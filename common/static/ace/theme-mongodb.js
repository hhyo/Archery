/* eslint-disable */
ace.define("ace/theme/mongodb",["require","exports","module","ace/lib/dom"], function(acequire, exports, module) {

exports.isDark = false;
exports.cssClass = "ace-mongodb";
exports.cssText = "\
.ace-mongodb .ace_gutter {\
background: #f5f6f7;\
color: #999999;\
}\
.ace-mongodb  {\
background: #f5f6f7;\
color: #000;\
}\
.ace-mongodb .ace_keyword {\
color: #999999;\
font-weight: normal;\
}\
.ace-mongodb .ace_gutter-cell {\
padding-left: 5px;\
padding-right: 10px;\
}\
.ace-mongodb .ace_string {\
color: #5b81a9;\
}\
.ace-mongodb .ace_boolean {\
color: #5b81a9;\
font-weight: normal;\
}\
.ace-mongodb .ace_constant.ace_numeric {\
color: #5b81a9;\
}\
.ace-mongodb .ace_string.ace_regexp {\
color: #5b81a9;\
}\
.ace-mongodb .ace_variable.ace_class {\
color: teal;\
}\
.ace-mongodb .ace_constant.ace_buildin {\
color: #0086B3;\
}\
.ace-mongodb .ace_support.ace_function {\
color: #0086B3;\
}\
.ace-mongodb .ace_comment {\
color: #998;\
font-style: italic;\
}\
.ace-mongodb .ace_variable.ace_language  {\
color: #0086B3;\
}\
.ace-mongodb .ace_paren {\
font-weight: normal;\
}\
.ace-mongodb .ace_variable.ace_instance {\
color: teal;\
}\
.ace-mongodb .ace_constant.ace_language {\
font-weight: bold;\
}\
.ace-mongodb .ace_cursor {\
color: #999999;\
}\
.ace-mongodb.ace_focus .ace_marker-layer .ace_active-line {\
background: #f5f6f7;\
}\
.ace-mongodb .ace_marker-layer .ace_active-line {\
background: rgb(245, 245, 245);\
}\
.ace-mongodb .ace_marker-layer .ace_selection {\
background: rgb(181, 213, 255);\
}\
.ace-mongodb.ace_multiselect .ace_selection.ace_start {\
box-shadow: 0 0 3px 0px white;\
}\
.ace-mongodb.ace_nobold .ace_line > span {\
font-weight: normal !important;\
}\
.ace-mongodb .ace_marker-layer .ace_step {\
background: rgb(252, 255, 0);\
}\
.ace-mongodb .ace_marker-layer .ace_stack {\
background: rgb(164, 229, 101);\
}\
.ace-mongodb .ace_marker-layer .ace_bracket {\
margin: -1px 0 0 -1px;\
border: 1px solid rgb(192, 192, 192);\
}\
.ace-mongodb .ace_gutter-active-line {\
background: #f5f6f7;\
}\
.ace-mongodb .ace_marker-layer .ace_selected-word {\
background: rgb(250, 250, 255);\
border: 1px solid rgb(200, 200, 250);\
}\
.ace-mongodb .ace_invisible {\
color: #BFBFBF\
}\
.ace-mongodb .ace_print-margin {\
width: 1px;\
background: #e8e8e8;\
}\
.ace-mongodb .ace_hidden-cursors {\
  opacity: 0;\
}\
.ace-mongodb .ace_indent-guide {\
background: url(\"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAACCAYAAACZgbYnAAAAE0lEQVQImWP4////f4bLly//BwAmVgd1/w11/gAAAABJRU5ErkJggg==\") right repeat-y;\
}";
  var dom = acequire("../lib/dom");
  dom.importCssString(exports.cssText, exports.cssClass);
});
