#!/usr/bin/perl

package saliweb::server;

use strict;


use CGI;
use Digest::MD5;
use File::Copy;

use saliweb::frontend;
use DBI;

use vars '@ISA', '@EXPORT', '$NAME', '$VERSION', '$DATE', '$AUTHOR';
require Exporter;
@ISA = qw(Exporter);
@EXPORT = qw(remote_user header validate_user validate_access);

$NAME = "saliweb::server";
$DATE = "9-09-2009";
$AUTHOR = "Ursula Pieper";

#
# -------------------------------------------------------------------------


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
    my $lab_navigation=shift@_;
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
        $title\n    </div>";
    $headertable.="\n    $lab_navigation\n    $navigation
        <div style=\"clear:both;\"></div><div id=\"bodypart\">";
    if ($current_project) {
        $headertable.=" \n<div id=\"left\">
          $current_project";
    }
    if ($menutitle ne "none") {
        $headertable.=
            "\n<div id=\"navigation_saliresources\">"
            ." <h3>$menutitle</h3> 
              <ul> $menuentries</ul>
            \n</div>";
    }
    if ($current_project) {
        $headertable.="\n</div><div id=\"right\">";
    } else {
        $headertable.="<div>";
    }

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
    my ($first,$last,$email,$modkey);

    if ($user_name ne "Anonymous") {
        if ($type eq "password") {
            $query="select user_name,password,first_name,last_name,email,"
                  ."modeller_key from "
                  ."$database.users where user_name=? and "
                  ." password=password(?) limit 1";
        } elsif ($type eq "hash") {
            $query="select user_name,password,first_name,last_name,email,"
                  ."modeller_key from $database.users where user_name=? "
                  ."and password=? limit 1";
        }
        $sth=$dbh->prepare($query) or die "cannot prepare: " .$dbh->errstr;
        $sth->execute($user_name, $password); # or die "cannot execute: " .$dbh->errstr;
        ($user_name,$hash,$first,$last,$email,$modkey)=$sth->fetchrow_array();
        if (defined($user_name)) {
            $userinfo{'name'}="$first $last";
            $userinfo{'email'}="$email";
            $userinfo{'modeller_key'}=$modkey;
        } else {
            $user_name = "Anonymous";
        }
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

1;
