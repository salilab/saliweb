var _id = 0, _pid = 0, _lid = 0, _pLayer;
var _mLists = new Array();
document.lists = _mLists;
var isNav4, isIE4;
if (parseInt(navigator.appVersion.charAt(0)) >= 4) {
  isNav4 = (navigator.appName == "Netscape") ? true : false;
  isIE4 = (navigator.appName.indexOf("Microsoft") != -1) ? true : false;
}
function List(visible, width, height, bgColor) {
  this.setIndent = setIndent;
  this.addItem = addItem;
  this.addList = addList;
  this.build = build;
  this.rebuild = rebuild;
  this.setFont = _listSetFont;
  this._writeList = _writeList;
  this._showList = _showList;
  this._updateList = _updateList;
  this._updateParent = _updateParent;
  this.onexpand = null; this.postexpand = null;
  this.lists = new Array(); // sublists
  this.items = new Array(); // layers
  this.types = new Array(); // type
  this.strs = new Array();  // content
  this.x = 0;
  this.y = 0;
  this.visible = visible;
  this.id = _id;
  this.i = 18;
  this.space = true;
  this.pid = 0;
  this.fontIntro = false;
  this.fontOutro = false;
  this.width = width || 350;
  this.height = height || 22;
  this.parLayer = false;
  this.built = false;
  this.shown = false;
  this.needsUpdate = false;
  this.needsRewrite = false;
  this.parent = null;
  this.l = 0;
  if(bgColor) this.bgColor = bgColor;
  else this.bgColor = null;
  _mLists[_id++] = this;
}
function _listSetFont(i,j) {
  this.fontIntro = i;
  this.fontOutro = j;
}
function setIndent(indent) { this.i = indent; if(this.i < 0) { this.i = 0; this.space = false; } }
function setClip(layer, l, r, t, b) {
  if(isNav4) {
    layer.clip.left = l; layer.clip.right = r;
    layer.clip.top = t;  layer.clip.bottom = b;
  } else {
    layer.style.pixelWidth = r-l;
    layer.style.pixelHeight = b-t;
    layer.style.clip = "rect("+t+","+r+","+b+","+l+")";
  }
}
function _writeList() {
  self.status = "List: Writing list...";
  var layer, str, clip;
  for(var i = 0; i < this.types.length; i++) { 
    layer = this.items[i];
    if(isNav4) layer.visibility = "hidden";
    else layer.style.visibility = "hidden";
    str = "";
    if(isNav4) layer.document.open();
    str += "<TABLE WIDTH="+this.width+" NOWRAP BORDER=0 CELLPADDING=0 CELLSPACING=0><TR>";
    if(this.types[i] == "list") {
      str += "<TD WIDTH=15 NOWRAP VALIGN=MIDDLE><A TARGET='_self' HREF=\"javascript:expand("+this.lists[i].id+");\"><IMG BORDER=0 SRC=\"/modbase-III/true.gif\" NAME=\"_img"+this.lists[i].id+"\"></A></TD>";
      _pid++;
    } else if(this.space)
      str += "<TD WIDTH=15 NOWRAP>&nbsp;</TD>";
    if(this.l>0 && this.i>0) str += "<TD WIDTH="+this.l*this.i+" NOWRAP>&nbsp;</TD>";
    str += "<TD HEIGHT="+(this.height-3)+" WIDTH="+(this.width-15-this.l*this.i)+" VALIGN=MIDDLE ALIGN=LEFT>";
    if(this.fontIntro) str += this.fontIntro;
    str += this.strs[i];
    if(this.fontOutro) str += this.fontOutro;
    str += "</TD></TABLE>";
    if(isNav4) {
      layer.document.writeln(str);
      layer.document.close();
    } else layer.innerHTML = str;
    if(this.types[i] == "list" && this.lists[i].visible)
      this.lists[i]._writeList();
  }
  this.built = true;
  this.needsRewrite = false;
  self.status = '';
}
function _showList() {
  var layer;
  for(var i = 0; i < this.types.length; i++) { 
    layer = this.items[i];
    setClip(layer, 0, this.width, 0, this.height-1);
    var bg = layer.oBgColor || this.bgColor;
    if(isIE4) {
      if((bg == null) || (bg == "null")) bg = "";
      layer.style.backgroundColor = bg;
    } else layer.document.bgColor = bg;
    if(this.types[i] == "list" && this.lists[i].visible)
      this.lists[i]._showList();
  }
  this.shown = true;
  this.needsUpdate = false;
}
function _updateList(pVis, x, y) {
  var currTop = y, layer;
  for(var i = 0; i < this.types.length; i++) { 
    layer = this.items[i];
    if(this.visible && pVis) {
      if(isNav4) {
        layer.visibility = "visible";
        layer.top = currTop;
        layer.left = x;
      } else {
        layer.style.visibility = "visible";
        layer.style.pixelTop = currTop;
        layer.style.pixelLeft = x;
      }
      currTop += this.height;
    } else {
      if(isNav4) layer.visibility = "hidden";
      else layer.style.visibility = "hidden";
    }
    if(this.types[i] == "list") {
      if(this.lists[i].visible) {
        if(!this.lists[i].built || this.lists[i].needsRewrite) this.lists[i]._writeList();
        if(!this.lists[i].shown || this.lists[i].needsUpdate) this.lists[i]._showList();
        if(isNav4) layer.document.images[0].src = "/modbase-III/true.gif";
        else eval('document.images._img'+this.lists[i].id+'.src = "/modbase-III\true.gif"');
      } else {
        if(isNav4) layer.document.images[0].src = "/modbase-III/false.gif";
        else eval('document.images._img'+this.lists[i].id+'.src = "/modbase-III/false.gif"');
      }
      if(this.lists[i].built)
        currTop = this.lists[i]._updateList(this.visible && pVis, x, currTop);
    }
  }
  return currTop;
}
function _updateParent(pid, l) {
  var layer;
  if(!l) l = 0;
  this.pid = pid;
  this.l = l;
  for(var i = 0; i < this.types.length; i++)
    if(this.types[i] == "list")
      this.lists[i]._updateParent(pid, l+1);
}
function expand(i) {
  _mLists[i].visible = !_mLists[i].visible;
  if(_mLists[i].onexpand != null) _mLists[i].onexpand(_mLists[i].id);
  _mLists[_mLists[i].pid].rebuild();
  if(_mLists[i].postexpand != null) _mLists[i].postexpand(_mLists[i].id);
}
function build(x, y) {
  this._updateParent(this.id);
  this._writeList();
  this._showList();
  this._updateList(true, x, y);
  this.x = x; this.y = y;
}
function rebuild() { this._updateList(true, this.x, this.y); }
function addItem(str, bgColor, layer) {
  var testLayer = false;
  if(!document.all) document.all = document.layers;
  if(!layer) {
    if(isIE4 || !this.parLayer) testLayer = eval('document.all.lItem'+_lid);
    else {
      _pLayer = this.parLayer;
      testLayer = eval('_pLayer.document.layers.lItem'+_lid);
    }
    if(testLayer) layer = testLayer;
    else {
      if(isNav4) {
        if(this.parLayer) layer = new Layer(this.width, this.parLayer);
        else layer = new Layer(this.width);
      } else return;
    }
  }
  if(bgColor) layer.oBgColor = bgColor;
  this.items[this.items.length] = layer;
  this.types[this.types.length] = "item";
  this.strs[this.strs.length] = str;
  _lid++;
}
function addList(list, str, bgColor, layer) {
  var testLayer = false;
  if(!document.all) document.all = document.layers;
  if(!layer) {
    if(isIE4 || !this.parLayer) testLayer = eval('document.all.lItem'+_lid);
    else {
      _pLayer = this.parLayer;
      testLayer = eval('_pLayer.document.layers.lItem'+_lid);
    }
    if(testLayer) layer = testLayer;
    else {
      if(isNav4) {
        if(this.parLayer) layer = new Layer(this.width, this.parLayer);
        else layer = new Layer(this.width);
      } else return;
    }
  }
  if(bgColor) layer.oBgColor = bgColor;
  this.lists[this.items.length] = list;
  this.items[this.items.length] = layer;
  this.types[this.types.length] = "list";
  this.strs[this.strs.length] = str;
  list.parent = this;
  _lid++;
}

function jumpPage(newLoc) {
	newPage = newLoc.options[newLoc.selectedIndex].value

	if (newPage != "") {
		window.location = newPage
	}
}



function launchHelp(helpurl) {
        //window.open("describe_datasets.cgi" + datasets, 'ModBaseDatasetDescription', 'width=500,height=200,scrollbars=yes,resizable=yes')
        helpWindow=window.open(helpurl, "ModBaseHelp", "width=500,height=600,scrollbars=yes,resizable=yes")
}
function launchDisplay(dataset_collection) {
        //window.open("describe_datasets.cgi" + datasets, 'ModBaseDatasetDescription', 'width=500,height=200,scrollbars=yes,resizable=yes')
        datasetWindow=window.open("describe_datasets.cgi" + dataset_collection, "ModBaseDatasetDescription", "width=500,height=200,scrollbars=yes,resizable=yes")
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

function gotoFunction() {
        self.location = document.userGoto.usernames.options[document.userGoto.usernames.selectedIndex].value;
}

function createCookie(name,value,days)
{
	if (days)
	{
		var date = new Date();
		date.setTime(date.getTime()+(days*24*60*60*1000));
		var expires = "; expires="+date.toGMTString();
	}
	else var expires = "";
	document.cookie = name+"="+value+expires+"; path=/";
}


function readCookie(name)
{
	var nameEQ = name + "=";
	var ca = document.cookie.split(';');
	for(var i=0;i < ca.length;i++)
	{
		var c = ca[i];
		while (c.charAt(0)==' ') c = c.substring(1,c.length);
		if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length);
	}
	return null;
}

function eraseCookie(name)
{
	createCookie(name,"",-1);
}

function saveModBaseCookie()
{
	var name = document.forms[0].modbase_user.value;
	var passwd = document.forms[0].modbase_passwd.value;
	var cookiename = "modbase-" + name;
	var cookievalue = "modbase_user&" + name + "&modbase_passwd&" + passwd ;

	if (!name)
		alert('Please Enter a User Name');
	else if (!passwd)
		alert('Please Enter the Password');
	else
		createCookie(cookiename,cookievalue,365);
}

function saveModWebCookie()
{
	var license= document.forms[0].modeller_license.value;
	var cookiename="modweb";
	var cookievalue=license;

	if (!license)
		alert('Please Enter the Modeller License Key');
	else
		createCookie(cookiename,cookievalue,365);
}

function SetAllCheckBoxes(FormName, FieldName, CheckValue)
{
	if(!document.forms[FormName])
		return;
	var objCheckBoxes = document.forms[FormName].elements[FieldName];
	if(!objCheckBoxes)
		return;
	var countCheckBoxes = objCheckBoxes.length;
	if(!countCheckBoxes)
		objCheckBoxes.checked = CheckValue;
	else
		// set the check value for all check boxes
		for(var i = 0; i < countCheckBoxes; i++)
			objCheckBoxes[i].checked = CheckValue;
}
