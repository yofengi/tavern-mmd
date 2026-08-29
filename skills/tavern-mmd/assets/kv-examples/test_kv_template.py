#!/usr/bin/env python3
"""Regression tests for the KV V4.0 three-stage document template."""

from html.parser import HTMLParser
from pathlib import Path
import json
import shutil
import subprocess
import unittest


STATUSBAR_MD = Path(__file__).resolve().parents[2] / "references" / "beautify" / "statusbar.md"
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class Element:
    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.parent = parent
        self.children = []

    @property
    def classes(self):
        return set(self.attrs.get("class", "").split())

    @property
    def element_children(self):
        return [child for child in self.children if isinstance(child, Element)]

    @property
    def next_element_sibling(self):
        if self.parent is None:
            return None
        siblings = self.parent.element_children
        index = siblings.index(self)
        return siblings[index + 1] if index + 1 < len(siblings) else None

    def descendants(self):
        for child in self.element_children:
            yield child
            yield from child.descendants()

    def first_descendant(self, predicate):
        return next((node for node in self.descendants() if predicate(node)), None)


class DocumentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element("#document")
        self.current = self.root

    def handle_starttag(self, tag, attrs):
        node = Element(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in VOID_TAGS:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        node = Element(tag, attrs, self.current)
        self.current.children.append(node)

    def handle_endtag(self, tag):
        node = self.current
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.current = node.parent


def extract_template(markdown, rule_number):
    section = markdown.index("### 规则%d：" % rule_number)
    fence = markdown.index("```\n", section) + 4
    end = markdown.index("\n```", fence)
    return markdown[fence:end]


def render_message(markdown, data_html):
    rendered = "<status>" + data_html
    for marker, rule_number in (
        ("<status>", 1),
        ("<!-- Z_CONTENT -->", 2),
        ("<!-- Z_SCRIPT -->", 3),
    ):
        template = extract_template(markdown, rule_number)
        if marker not in rendered:
            raise AssertionError("template marker missing before rule %d: %s" % (rule_number, marker))
        rendered = rendered.replace(marker, template, 1)
    return rendered


def parse_document(html):
    parser = DocumentParser()
    parser.feed(html)
    parser.close()
    return parser.root


def nodes_with_class(document, class_name):
    return [node for node in document.descendants() if class_name in node.classes]


def data_box_for(document, target_box):
    nested = target_box.first_descendant(lambda node: "z-status-data" in node.classes)
    if nested is not None:
        return nested

    next_node = target_box.next_element_sibling
    if next_node is not None:
        if "z-status-data" in next_node.classes:
            return next_node
        wrapped = next_node.first_descendant(lambda node: "z-status-data" in node.classes)
        if wrapped is not None:
            return wrapped

    ordered = [
        node for node in document.descendants()
        if "z-status-box" in node.classes or "z-status-data" in node.classes
    ]
    seen = False
    for node in ordered:
        if node is target_box:
            seen = True
            continue
        if seen:
            if "z-status-box" in node.classes:
                break
            if "z-status-data" in node.classes:
                return node
    return None


def find_data(document, box, data_attr, current_only=False, field=None):
    def pick(data_box):
        if data_box is None:
            return None
        found = data_box.first_descendant(lambda node: data_attr in node.attrs)
        if found is not None and (field is None or field in found.attrs):
            return found
        return None

    found = pick(data_box_for(document, box))
    if found is not None or current_only:
        return found

    boxes = nodes_with_class(document, "z-status-box")
    index = boxes.index(box)
    for previous in reversed(boxes[:index]):
        found = pick(data_box_for(document, previous))
        if found is not None:
            return found
    return None


class KvTemplateRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.markdown = STATUSBAR_MD.read_text(encoding="utf-8")
        first_data = (
            '<div class="z-status-data" style="display:none">'
            '<div data-env tm="day-1" loc="library" rd="old-note"></div>'
            '<div data-st zy="hp:85/100"></div>'
            '<div data-opt c1="wait|desc|low|safe"></div>'
            '</div>'
        )
        second_data = (
            '<div class="z-status-data" style="display:none">'
            '<div data-env rd="new-note"></div>'
            '<div data-st zy="hp:65/100"></div>'
            '<div data-opt c1="search|desc|medium|normal"></div>'
            '</div>'
        )
        first = render_message(cls.markdown, first_data)
        second = render_message(cls.markdown, second_data)
        cls.rendered = (
            '<main><article id="round-1">' + first + '</article>'
            '<article id="round-2">' + second + '</article></main>'
        )
        cls.document = parse_document(cls.rendered)

    def test_full_pipeline_pairs_each_box_with_its_sibling_data(self):
        boxes = nodes_with_class(self.document, "z-status-box")
        data_boxes = nodes_with_class(self.document, "z-status-data")
        self.assertEqual(2, len(boxes))
        self.assertEqual(2, len(data_boxes))
        self.assertNotIn("<!-- Z_CONTENT -->", self.rendered)
        self.assertNotIn("<!-- Z_SCRIPT -->", self.rendered)

        for index, box in enumerate(boxes):
            self.assertIsNone(box.first_descendant(lambda node: "z-status-data" in node.classes))
            self.assertIs(data_boxes[index], box.next_element_sibling)
            self.assertIs(data_boxes[index], data_box_for(self.document, box))

    def test_current_data_and_attribute_level_history_are_reachable(self):
        current_box = nodes_with_class(self.document, "z-status-box")[1]
        current_rd = find_data(self.document, current_box, "data-env", field="rd")
        inherited_tm = find_data(self.document, current_box, "data-env", field="tm")
        inherited_loc = find_data(self.document, current_box, "data-env", field="loc")
        current_opt = find_data(self.document, current_box, "data-opt", current_only=True)

        self.assertEqual("new-note", current_rd.attrs["rd"])
        self.assertEqual("day-1", inherited_tm.attrs["tm"])
        self.assertEqual("library", inherited_loc.attrs["loc"])
        self.assertEqual("search|desc|medium|normal", current_opt.attrs["c1"])

    def test_generated_handler_keeps_dynamic_bindings_and_input_fallback(self):
        box = nodes_with_class(self.document, "z-status-box")[0]
        image = box.first_descendant(lambda node: node.tag == "img" and "onerror" in node.attrs)
        self.assertIsNotNone(image)
        handler = image.attrs["onerror"]
        self.assertIn("tabs[ti].onclick=function", handler)
        self.assertIn("btn.onclick=function", handler)
        self.assertIn(".uni-textarea-textarea,textarea,input[type=text]", handler)
        self.assertIn("dataBoxFor(box)", handler)

    @unittest.skipUnless(shutil.which("node"), "Node.js is required to execute the generated onerror handler")
    def test_generated_onerror_clicks_option_into_plain_text_input(self):
        box = nodes_with_class(self.document, "z-status-box")[0]
        image = box.first_descendant(lambda node: node.tag == "img" and "onerror" in node.attrs)
        handler = image.attrs["onerror"]
        script = r'''
"use strict";
var inputEvents=0,stopped=0,removed=0,optionButton=null;
function Elem(tag){this.tagName=tag.toUpperCase();this.attrs={};this.children=[];this.value="";this.className="";this.textContent="";}
Elem.prototype.setAttribute=function(k,v){this.attrs[k]=String(v)};
Elem.prototype.getAttribute=function(k){return Object.prototype.hasOwnProperty.call(this.attrs,k)?this.attrs[k]:null};
Elem.prototype.hasAttribute=function(k){return Object.prototype.hasOwnProperty.call(this.attrs,k)};
Elem.prototype.appendChild=function(c){this.children.push(c);if(c.className.indexOf("z-status-opt ")===0)optionButton=c;return c};
Elem.prototype.removeChild=function(c){var i=this.children.indexOf(c);if(i>=0)this.children.splice(i,1);return c};
Object.defineProperty(Elem.prototype,"firstChild",{get:function(){return this.children[0]||null}});
Elem.prototype.querySelector=function(sel){if(sel===".z-status-data")return null;if(sel==="[data-list=opts]")return optionGrid;if(sel.indexOf("[data-field=")===0||sel.indexOf("[data-list=")===0)return null;return null};
Elem.prototype.querySelectorAll=function(sel){if(sel===".z-status-env-tab"||sel===".z-status-env-panel")return[];return[]};
function Event(type,opts){this.type=type;this.bubbles=!!(opts&&opts.bubbles)}
var plainInput=new Elem("input");plainInput.setAttribute("type","text");plainInput.dispatchEvent=function(ev){if(ev.type==="input"&&ev.bubbles)inputEvents++};
var optionGrid=new Elem("div");
var opt=new Elem("div");opt.setAttribute("data-opt","");opt.setAttribute("c1","search|desc|low|safe");
var dataBox={classList:{contains:function(v){return v==="z-status-data"}},querySelector:function(sel){return sel==="div[data-opt]"?opt:null}};
var box=new Elem("div");box.nextElementSibling=dataBox;box.closest=function(){return box};
var img={closest:function(){return box},remove:function(){removed++}};
var document={
 querySelector:function(sel){if(sel===".chatMsgTextarea")return null;if(sel===".uni-textarea-textarea,textarea,input[type=text]")return plainInput;return null},
 querySelectorAll:function(sel){if(sel===".z-status-box")return[box];if(sel===".z-status-box,.z-status-data")return[box,dataBox];return[]},
 createElement:function(tag){return new Elem(tag)}
};
(function(){HANDLER;}).call(img);
if(!optionButton||typeof optionButton.onclick!=="function")throw new Error("generated option click handler missing");
optionButton.onclick.call(optionButton,{stopPropagation:function(){stopped++}});
if(plainInput.value!==" search")throw new Error("plain input fallback failed: "+plainInput.value);
if(inputEvents!==1||stopped!==1||removed!==1)throw new Error("event/remove contract failed: "+[inputEvents,stopped,removed]);
process.stdout.write(JSON.stringify({value:plainInput.value,inputEvents:inputEvents,stopped:stopped,removed:removed}));
'''.replace("HANDLER", handler)
        completed = subprocess.run(
            [shutil.which("node"), "-e", script],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        result = json.loads(completed.stdout)
        self.assertEqual(" search", result["value"])
        self.assertEqual(1, result["inputEvents"])
        self.assertEqual(1, result["stopped"])
        self.assertEqual(1, result["removed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
