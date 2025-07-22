from utils.constants import SELF_CLOSING_TAGS, HEAD_TAGS, INHERITED_PROPERTIES
import html.entities
class Element:
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.attributes = attributes
        self.children = []
        self.parent = parent

    def __repr__(self):
        attrs = [" " + k + "=\"" + v + "\"" for k, v  in self.attributes.items()]
        attr_str = ""
        for attr in attrs:
            attr_str += attr
        return "<" + self.tag + attr_str + ">"

class Text:
    def __init__(self, text, parent):
        self.text = text
        self.children = []
        self.parent = parent

    def __repr__(self):
        return repr(self.text)

class HTML():
    def __init__(self, raw_html):
        self.raw_html = raw_html
        self.unfinished = []

        self.parse()
    
    def parse(self):
        text = ""
        in_tag = False
        for c in self.raw_html:
            if c == "<":
                in_tag = True
                if text: self.add_text(text) # start of new tag means before everything was content/text
                text = ""
            elif c == ">":
                in_tag = False
                self.add_tag(text) # end of a tag means everything in-between were tags
                text = ""
            else:
                text += c
        
        if not in_tag and text:
            self.add_text(text)

        return self.finish()

    def add_text(self, text):
        if text.isspace(): return
        self.implicit_tags(None)
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)

    def get_attributes(self, text):
        parts = text.split()
        tag = parts[0].casefold()
        attributes = {}
        
        for attrpair in parts[1:]:
            if "=" in attrpair:
                key, value = attrpair.split("=", 1)
                if len(value) > 2 and value[0] in ["'", "\""]:
                    value = value[1:-1]
                attributes[key.casefold()] = value
            else:
                attributes[attrpair.casefold()] = ""

        return tag, attributes

    def add_tag(self, tag):
        tag, attributes = self.get_attributes(tag)
        
        if tag.startswith("!"): return
        
        self.implicit_tags(tag)

        if tag.startswith("/"):
            if len(self.unfinished) == 1: return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        elif tag in SELF_CLOSING_TAGS:
            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            parent.children.append(node)
        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(tag, attributes, parent)
            self.unfinished.append(node)

    def implicit_tags(self, tag):
        while True:
            open_tags = [node.tag for node in self.unfinished]
            if open_tags == [] and tag != "html":
                self.add_tag("html")
            elif open_tags == ["html"] and tag not in ["head", "body", "/html"]:
                if tag in HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")
            elif open_tags == ["html", "head"] and tag not in ["/head"] + HEAD_TAGS:
                self.add_tag("/head")
            else:
                break

    def finish(self):
        if not self.unfinished:
            self.implicit_tags(None)
    
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        return self.unfinished.pop()
    
    @staticmethod
    def print_tree(node, indent=0):
        print(" " * indent, node)
        for child in node.children:
            HTML.print_tree(child, indent + 2)

    @staticmethod
    def to_json(tree: Element | Text):
        if isinstance(tree, Text):
            return ["text", tree.text, [HTML.to_json(child) for child in tree.children]]
        elif isinstance(tree, Element):
            return ["element", tree.tag, tree.attributes, [HTML.to_json(child) for child in tree.children]]

    @staticmethod
    def from_json(json_list, parent=None):
        if json_list[0] == "text":
            text = Text(json_list[1], parent)
            text.children = [HTML.from_json(child, text) for child in json_list[2]]
            return text
        elif json_list[0] == "element":
            element = Element(json_list[1], json_list[2], parent)
            element.children = [HTML.from_json(child, element) for child in json_list[3]]
            return element
        
class TagSelector:
    def __init__(self, tag):
        self.tag = tag
        self.priority = 1
    
    def matches(self, node):
        return isinstance(node, Element) and self.tag == node.tag
    
class DescendantSelector:
    def __init__(self, ancestor, descendant):
        self.ancestor = ancestor
        self.descendant = descendant
        self.priority = ancestor.priority + descendant.priority

    def matches(self, node):
        if not self.descendant.matches(node): return False
        while node.parent:
            if self.ancestor.matches(node.parent): return True
            node = node.parent
        return False

def cascade_priority(rule):
    selector, body = rule
    return selector.priority

def get_inline_styles(node):
    all_rules = []

    for node in node.children:
        if isinstance(node, Element) and node.tag == "style":
            if isinstance(node.children[0], Text):
                all_rules.extend(CSSParser(node.children[0].text).parse()) # node's first children will just be a text element that contains the css

        all_rules.extend(get_inline_styles(node))
    
    return all_rules

class CSSParser:
    def __init__(self, s):
        self.s = s
        self.i = 0

    def whitespace(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def literal(self, literal):
        if not (self.i < len(self.s) and self.s[self.i] == literal):
            raise Exception("Parsing error")
        self.i += 1

    def word(self):
        start = self.i
        while self.i < len(self.s):
            if self.s[self.i].isalnum() or self.s[self.i] in "#-.%":
                self.i += 1
            else:
                break
        if not (self.i > start):
            raise Exception("Parsing error")
        return self.s[start:self.i]
        
    def pair(self):
        prop = self.word()
        
        self.whitespace()
        self.literal(":")
        self.whitespace()
        
        val = self.word()

        return prop.casefold(), val

    def ignore_until(self, chars):
        while self.i < len(self.s):
            if self.s[self.i] in chars:
                return self.s[self.i]
            else:
                self.i += 1
        return None

    def body(self):
        pairs = {}
        while self.i < len(self.s) and self.s[self.i] != "}":
            try:
                prop, val = self.pair()
                pairs[prop] = val
                
                self.whitespace()
                
                self.literal(";")

                self.whitespace()        
            except Exception:
                why = self.ignore_until([";", "}"])
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break

        return pairs
    
    def selector(self):
        out = TagSelector(self.word().casefold())
        self.whitespace()
        while self.i < len(self.s) and self.s[self.i] != "{":
            tag = self.word()
            descendant = TagSelector(tag.casefold())
            out = DescendantSelector(out, descendant)
            self.whitespace()
        return out
        
    def parse(self):
        rules = []
        while self.i < len(self.s):
            try:
                self.whitespace()
                
                selector = self.selector()
                
                self.literal("{")
                
                self.whitespace()
                
                body = self.body()
                
                self.literal("}")

                rules.append((selector, body))
            except Exception:
                why = self.ignore_until(["}"])
                if why == "}":
                    self.literal("}")
                    self.whitespace()
                else:
                    break
        return rules
    
    @classmethod
    def convert_selector_to_json(self, selector):
        if isinstance(selector, TagSelector):
            return ["tag", selector.tag, selector.priority]
        elif isinstance(selector, DescendantSelector):
            return ["descendant", self.convert_selector_to_json(selector.ancestor), self.convert_selector_to_json(selector.descendant)]
        
    @classmethod
    def get_selector_from_json(self, selector_list):
        if selector_list[0] == "tag":
            selector = TagSelector(selector_list[1])
            selector.priority = selector_list[2]
            return selector
        elif selector_list[0] == "descendant":
            return DescendantSelector(self.get_selector_from_json(selector_list[1]), self.get_selector_from_json(selector_list[2]))

    @classmethod
    def to_json(self, rules_list: list[tuple[TagSelector | DescendantSelector, dict[str, str]]]):
        return [[self.convert_selector_to_json(rule[0]), rule[1]] for rule in rules_list]

    @classmethod
    def from_json(self, rules_list):
        return [(self.get_selector_from_json(rule[0]), rule[1]) for rule in rules_list]

def style(node, rules):
    node.style = {}

    for property, default_value in INHERITED_PROPERTIES.items():
        if node.parent:
            node.style[property] = node.parent.style[property]
        else:
            node.style[property] = default_value

    for selector, body in rules:
        if not selector.matches(node): continue
        for property, value in body.items():
            node.style[property] = value

    if isinstance(node, Element) and "style" in node.attributes:
        pairs = CSSParser(node.attributes["style"]).body()
        for property, value in pairs.items():
            node.style[property] = value 

    if node.style["font-size"].endswith("%"):
        if node.parent:
            parent_font_size = node.parent.style["font-size"]
        else:
            parent_font_size = INHERITED_PROPERTIES["font-size"]

        node_pct = float(node.style["font-size"][:-1]) / 100
        parent_px = float(parent_font_size[:-2])
        node.style["font-size"] = str(node_pct * parent_px) + "px"

    for child in node.children:
        style(child, rules)

def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list

def replace_symbols(text):
    for key, value in html.entities.html5.items():
        text = text.replace(f"&{key};", value)

    return text