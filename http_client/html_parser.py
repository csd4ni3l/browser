SELF_CLOSING_TAGS = [
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
]

HEAD_TAGS = [
    "base", "basefont", "bgsound", "noscript",
    "link", "meta", "title", "style", "script",
]

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