#!/usr/bin/perl

package saliweb::server;

use strict;


use CGI;
use CGI::Carp qw(fatalsToBrowser);
use CGI::Pretty;
use Digest::MD5;
use File::Copy;

use saliweb::frontend;
use DBI;

use vars '@ISA', '@EXPORT', '$NAME', '$VERSION', '$DATE', '$AUTHOR';
require Exporter;
@ISA = qw(Exporter);
@EXPORT = qw(help_link remote_user header validate_user get_datetime upload_file get_seq_id CleanSeq make_seq_id format_sequence check_file end_server add_user validate_access navigation validate_email get_dir_list );

$NAME = "saliweb::server";
$DATE = "9-09-2009";
$AUTHOR = "Ursula Pieper";

#
# -------------------------------------------------------------------------


sub help_link {

    my $server=shift @_;
    my $keyword=shift @_;
    my $help_link;
    my $q=new CGI;
    my ($url);
    if (grep/^http/,$keyword) {
        $url=$keyword;
    } else {
        $url="display?server=$server&style=helplink&type=help#$keyword";
    }

    $help_link=$q->a({-href=>"$url",-border=>"0", -onClick=>"launchHelp(\'$url\'); return false;"},
            $q->img({-src=>"/img/help.jpg", -border=>0,-valign=>"bottom"} ));

    return $help_link;
}

sub remote_user {

        my $q= new CGI;
        my ($current_user,$remote_host);
        $current_user=$ENV{'REMOTE_USER'};
        $remote_host=$ENV{"REMOTE_HOST"}||$ENV{'REMOTE_ADDR'};
        return ($remote_host);
}

sub header {
    my $root=shift @_;
    my $title=shift @_;
    my $menutitle=shift@_;
    my $menuentries_ref=shift@_;
    my $current_project=shift@_;
    my $navigation=shift@_;
    my %menuentries;
    if ($menuentries_ref) {
        %menuentries=%$menuentries_ref;
    } 
        
    my $q=new CGI;
    my ($headertable,$field,$linkline);
    my ($remote_host)=&remote_user;
        my ($menuentries,$entry);
        foreach $entry (sort keys %menuentries) {
            
            if ($menuentries{$entry} eq "not available") {
                $menuentries.="<li>$entry</li>\n";
            } else {
                $menuentries.="<li><a href=\"".$menuentries{$entry}."\">$entry</a></li>\n";
            }
    }
              
    $headertable="<div id=\"container\">\n    <div id=\"header1\"> 
        <h3><img src=\"http://salilab.org/img/logo_small.gif\" height=\"40\" alt=\"\" /> $title</h3>\n    </div>";
    $headertable.="\n    <div id=\"navigation_lab\">\n
            &bull;&nbsp;<a href=\"http://salilab.org\">Sali Lab Home</a>&nbsp;&bull;&nbsp;

        <a href=\"http://salilab.org/modweb\"> ModWeb</a>&nbsp;&bull;&nbsp;
        <a href=\"http://salilab.org/modbase/\">ModBase</a>&nbsp;&bull;&nbsp;
        <a href=\"http://salilab.org/imp/\">IMP</a>&nbsp;&bull;&nbsp;
        <a href=\"http://salilab.org/modpipe/\">ModPipe</a>&nbsp;&bull;&nbsp;
        <a href=\"http://salilab.org/LS-SNP/\">LS-SNP</a>&nbsp;&bull;&nbsp;
    \n</div>\n    $navigation
        <div style=\"clear:both;\"></div><div id=\"bodypart\">";
    $headertable.=" \n<div id=\"left\">
          $current_project";
    if ($menutitle ne "none") {
        $headertable.=
            "\n<div id=\"navigation_saliresources\">"
            ." <h3>$menutitle</h3> 
              <ul> $menuentries</ul>
            \n</div>";
    }
    $headertable.="\n</div>";

    return $headertable;
    
}

sub validate_user {

    my $dbh=shift @_;
    my $database=shift @_;
    my $type=shift @_;
    my $user_name=shift @_;
    my $password=shift @_;
    my $server=shift @_;
    my ($query,$sth,@row,$hash);
    my %userinfo;
    my ($first,$last,$email);

    if ($user_name ne "Anonymous") {
        if ($type eq "password") {
            $query="select user_name,password,first_name,last_name,email from "
                  ."$database.users where user_name='$user_name' and "
                  ." password=password('$password') limit 1";
        } elsif ($type eq "hash") {
            $query="select user_name,password,first_name,last_name,email from "
            ."$database.users where user_name='$user_name' and password='$password' limit 1";
        }
        $sth=$dbh->prepare($query);
        $sth->execute();
        ($user_name,$hash,$first,$last,$email)=$sth->fetchrow_array();
        $userinfo{'name'}="$first $last";
        $userinfo{'email'}="$email";
    } elsif ($user_name eq "Anonymous") {
        $hash="";
    }
    if (($user_name eq "Anonymous") || ($user_name && $hash)) {
        if ($server) {
            my $access=&validate_access($dbh,$database,$user_name,$server);
            if ($access eq "not validated") {
                return ("Access not validated");
            } else {
                return($user_name,$hash,\%userinfo);
            }
        } else {
            return($user_name,$hash,\%userinfo);
        }
    } else {
        return ("User not validated");
    }
}
 
sub add_user {
    my $dbh=shift @_;
    my $database=shift @_;
    my $user_name=shift @_;
    my $password=shift @_;
    my $first_name=shift @_;
    my $last_name=shift @_;
    my $institution=shift @_;
    my $email=shift @_;
    my $ip=shift @_;
       
    my ($query, $sth, @row,$existing_user_name);

    $query="select user_name from $database.users where user_name='$user_name' limit 1";
    $sth=$dbh->prepare($query);
    $sth->execute();
    ($existing_user_name)=$sth->fetchrow_array();
    if ($existing_user_name) {
        &end_server("noheader","User Name $user_name already exists, please go back and choose a different User Name!");
    } else {
        my $datetime=&get_datetime("datetime");
        my $insert=" insert into $database.users (user_name,password, ip_addr, first_name, last_name, "
            ."email, institution,date_added) values ('$user_name',password('$password'), "
            ." '$ip', '$first_name', '$last_name', '$email', '$institution','$datetime')";
        $dbh->do($insert) or &end_server("noheader","insert username failed, please email the web-master.");
    }
    my $hash;
    ($user_name,$hash)=&validate_user($dbh,'servers','password',$user_name,$password);
    return $hash;
}

sub get_datetime {
    
    my $type=shift @_;
    my ($sec,$min,$hour,$mday,$mon,$year,$wday,
        $yday,$isdst)=localtime();
    my ($date,$datetime);
    $datetime=sprintf "%4d%02d%02d%02d%02d%02d", $year+1900,$mon+1,$mday,$hour,$min,$sec;
    $date=sprintf "%4d%02d%02d", $year+1900,$mon+1,$mday;
    if ($type eq "date") {
        return $date;
    } else {
        return $datetime;
    }
}

sub upload_file {

    my $type=shift@_;
    my $upload=shift@_;
    my $path=shift@_;
    my ($file,$bytesread,$buffer,$save);

    use constant UPLOAD_DIR => $path;
    use constant BUFFER_SIZE => 16_384;
    use constant MAX_FILE_SIZE => 2_048_576;
    use constant MAX_DIR_SIZE => 2000*1_048_576;
    use constant MAX_OPEN_TRIES => 2000;

    $CGI::DISABLE_UPLOADS   = 0;
    $CGI::POST_MAX          = MAX_FILE_SIZE;

    if ($path) {
        $save=$upload;
        $save=~m/^.*(\\|\/)(.*)/;
        $save=&check_file($path,$save);

        eval        {open (OUTFILE,">$path/$save")} or do
                    {&end_server("header","Error at file-upload $path/$save, "
                    ." file possibly already exists, change filename?")};

    } 
    while ($bytesread=read($upload,$buffer,1024)) {
        $file.=$buffer;
        if ($path) {
            print OUTFILE $buffer;
        }
    }

    if ($path) {
        close OUTFILE;
    }

    if ($path) {
        if ($type eq "model") {
            my $md5= new Digest::MD5;

                # --- generate sequence digest
            $md5->reset();
            $md5->add($file);
            my $model_id= $md5->hexdigest();

            move("$path/$save","/$path/$model_id.pdb"); 
#        &end_modbase($path, $upload, $save);
            return ($save,$model_id);
        } else {
            return ($save);
        }
    } else {
        return $file;
    }
}

    
sub get_seq_id {

        my $inputsequence=shift @_;
        my ($seq_id,$sequence);

        $sequence = &CleanSeq($inputsequence,"modpipe");   # clean up the seq from the form
        $seq_id=&make_seq_id($sequence);
        return $seq_id;

}

sub CleanSeq {

   # --- Reassign input arguments
   my $sequence = shift @_;
   my $type = shift @_;

   # --- Clean up sequence
   if ($sequence) {
       $sequence =~ s/\n//mg;    # --- make one line
       $sequence =~ s/\r//mg;    # --- make one line
       $sequence =~ s/\W+//g;    # --- eliminate non-word char
       $sequence =~ s/_+//g;     # --- eliminate underscore, since not covered by \W
       $sequence =~ s/\d+//g;    # --- eliminate numbers
       $sequence =~ s/\*//;      # --- eliminate *'s
       $sequence =~ s/\s+//g;    # --- eliminate spaces
       $sequence =~ tr/a-z/A-Z/; # --- convert to uppercase
       $sequence =~ s/B/N/g;     # --- convert ASX to ASN
       $sequence =~ s/Z/Q/g;     # --- convert GLX to GLN
       $sequence =~ s/[^ACDEFGHIKLMNPQRSTVWY]/G/g; # --- convert everything else to GLY
          return $sequence;
   } 

}

sub make_seq_id {
        my $sequence=shift @_;
        my $md5= new Digest::MD5;
        my ($seq_id);

        # --- generate sequence digest
        $md5->reset();
        $md5->add($sequence);
        $seq_id= $md5->hexdigest();
        $seq_id=$seq_id.substr($sequence,0,4).substr($sequence,-4);
        return ($seq_id);
}

sub format_sequence {
        my $sequence=shift @_;
        my ($i,$seqlength,$print_sequence,$j);
        $seqlength=length($sequence);
        $i=int($seqlength/50);
        for ($j=0;$j<=$i;$j++) {
                $print_sequence =$print_sequence.substr($sequence,$j*50,50)."\n";
        }
        return ($print_sequence);
}

sub check_file {

        my $path=shift @_;
        my $save=shift @_;
        if (-e "$path/$save") {
                $save=$save."_1";
                $save=&check_file($path,$save);
        }
        return $save;
}
sub end_server {
    my $q=new CGI;
        my $type=shift @_;
    my @message=@_;
        if ($type eq "header") {
        print $q->header,$q->start_html;
        }
    print   $q->table({-width=>"100%",-border=>0,-cellpadding=>"0",-cellspacing=>"0",-align=>"center"},
        $q->Tr($q->td("&nbsp;")));

        my $errortable=$q->table( $q->Tr( $q->td({-class=>"redtxt", -align=>"left"},$q->h3("Server Error:"))),
                $q->Tr( $q->td($q->b("An error occured during your request:"))),
                $q->Tr( $q->td("<div class=standout>" ,
            $q->pre(join($q->br,@message)),"</div>",$q->br)),
                $q->Tr( $q->td( $q->b("Please click on your browser's \"BACK\" button, and correct the problem.",$q->br))));

        print $errortable;
        print $q->end_html;
        exit;
}

sub validate_access {

    my $dbh=shift @_;
    my $database=shift @_;
    my $user_name=shift@_;
    my $server=shift @_;
    my ($query,$sth,$return,@row);
    $query="select user_name from $database.access where (user_name='$user_name' "
          ." or user_name='Anonymous')"
          ." and server='$server'";
    $sth=$dbh->prepare($query);
    $sth->execute();
    @row=$sth->fetchrow_array();
    if ($row[0] eq $user_name) {
        return $user_name;
    } else {
        return "not validated";
    }
}

sub navigation {

    my $dbh=shift @_;
    my $cgiroot=shift @_;
    my $user_name=shift @_;
    my ($field,%list,$navigation_table,$userlink);
    my $q=new CGI;

    my %projects;
    
    if (!$user_name) {
        $user_name="Anonymous";
    }
    %list = (
        "user" => $q->a({-href=>"server.cgi"},"Current User:$user_name"),
        "logout" => $q->a({-href=>"server.cgi?logout=true"},"Logout"),
        "home" => $q->a({-href=>"$cgiroot/server.cgi"},"Sali Lab Server Home"),
        "help" => $q->a({-href=>"$cgiroot/display?type=help&server=server"},"Help"),
        "news" => $q->a({-href=>"$cgiroot/display?type=news&server=server"},"News"),
        "contact" => $q->a({-href=>"$cgiroot/display?type=contact&server=server"},"Contact"));


    foreach $field (keys %list) {
        $navigation_table.=$list{$field}."&nbsp;&bull;&nbsp;\n";
    }
    $navigation_table="<div id=navigation_second>$navigation_table</div>";
  
    return ($navigation_table);

}
sub validate_modeller {
    my $key=shift @_;
    if (uc($key) ne "***REMOVED***") {
         &end_server("header","ModWeb Error: Please enter a valid MODELLER access "
                    ."key. <br/> Visit the "
                    ."<a href=\"http://salilab.org/modeller/registration.html\">"
                    ."MODELLER Registration</a> page to get one.");
    } else {
        return "validated";
    }
}
sub validate_email {
 
    my $type=shift@_;
    my $email=shift@_;
    my $essential=shift@_;
    my $key;
    if ($type) {
        if (grep/salilab/,$email) {
            $key="verified";
        } elsif (grep/$type/,$email) {
            &end_server("header","$type Error: Please provide valid return email address");
        }
    }
    if ($email =~ m/^[\w\.-]+@[\w-]+\.[\w-]+((\.[\w-]+)*)?$/ ) {
        return ("validated",$key);
    } else {
        if ($essential eq "ignore") {
            return("noemail",$key);
        } else {
            &end_server("header","ModWeb Error: Please provide valid return email address");
        }
    }
}

sub get_dir_list {

   my $dir =shift @_ ;
   # -- Get the list of files in folder
   unless ( opendir(DIR, $dir) ){
      &end_server("header","Could not open folder\n");
      return;
   }

   my @files = ();
   while ( my $file = readdir(DIR) ){
      next if ( $file =~ /^\..*/ );
      push @files, $file;
   }
   closedir(DIR);

   # -- return
   return @files;
}

1;


