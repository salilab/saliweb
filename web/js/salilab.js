function launchHelp(helpurl) {
        //window.open("describe_datasets.cgi" + datasets, 'ModBaseDatasetDescription', 'width=500,height=200,scrollbars=yes,resizable=yes')
        helpWindow=window.open(helpurl, "ModBaseHelp", "width=500,height=600,scrollbars=yes,resizable=yes")
}

function escramble(user,domain){
 var a,b,c,d,e,f,g,h,i
 a='<a href=\"mai'
 b=user
 c='\">'
 a+='lto:'
 b+='\@'
 e='</a>'
 f=''
 b+=domain
 g='<img src=\\"'
 h=''
 i='\\" alt="Email us." border="0">'

 if (f) d=f
 else if (h) d=g+h+i
 else d=b

 document.write(a+b+c+d+e)
}

function toggle_visibility_tbody(id, linkid) {
  var e = document.getElementById(id);
  var lnk = document.getElementById(linkid);
  if(e.style.display == 'table-row-group') {
    e.style.display = 'none';
    lnk.innerHTML = lnk.innerHTML.replace('Hide', 'Show');
  } else {
    e.style.display = 'table-row-group';
    lnk.innerHTML = lnk.innerHTML.replace('Show', 'Hide');
  }
}

function toggle_visibility(id, linkid) {
  var e = document.getElementById(id);
  var lnk = document.getElementById(linkid);
  if(e.style.display == 'block') {
    e.style.display = 'none';
    lnk.innerHTML = lnk.innerHTML.replace('Hide', 'Show');
  } else {
    e.style.display = 'block';
    lnk.innerHTML = lnk.innerHTML.replace('Show', 'Hide');
  }
}

function convert_utc_dates_to_local() {
  var e = document.getElementById('queue');
  var nrows = e.rows.length;
  var first = true;
  var d = new Date();
  var style = window.getComputedStyle(document.documentElement, null);
  var max_width = style.getPropertyValue("max-width");
  for (var i = 0; i < nrows; i++) {
    if (e.rows[i].cells.length == 3) {
      if (first) {
        first = false;
        e.rows[i].cells[1].innerHTML = "Submit time";
      } else {
        var inner = e.rows[i].cells[1].innerHTML;
        d.setUTCFullYear(inner.substr(0, 4));
        d.setUTCMonth(inner.substr(5, 2) - 1, inner.substr(8, 2));
        d.setUTCHours(inner.substr(11, 2));
        d.setUTCMinutes(inner.substr(14, 2));
        d.setUTCSeconds(inner.substr(17, 2));
        if (max_width == "970px") {
          e.rows[i].cells[1].innerHTML = d.toDateString();
        } else {
          e.rows[i].cells[1].innerHTML = d.toString();
        }
      }
    }
  }
}
