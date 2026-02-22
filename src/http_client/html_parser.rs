use crate::constants::*;
use std::collections::HashMap;

#[derive(Clone)]
pub struct Element {
    pub tag: String,
    pub children: Vec<Node>,
    pub attributes: HashMap<String, String>,
    pub parent: Option<Box<Node>>
}

#[derive(Clone)]
pub struct Text {
    pub text: String,
    pub children: Vec<Node>,
    pub parent: Option<Box<Node>>
}

#[derive(Clone)]
pub enum Node {
    Element(Element),
    Text(Text),
}

impl Node {
    pub fn tag(&self) -> Option<&str> {
        match self {
            Node::Element(e) => Some(&e.tag),
            Node::Text(_) => None
        }
    }

    pub fn children(&self) -> &Vec<Node> {
        match self {
            Node::Element(e) => &e.children,
            Node::Text(t) => &t.children
        }
    }

    pub fn parent(&self) -> Option<&Node> {
        match self {
            Node::Text(t) => t.parent.as_deref(),
            Node::Element(e) => e.parent.as_deref(),
        }
    }
}

pub struct HTML {
    pub raw_html: String,
    pub unfinished: Vec<Element>,
}

impl HTML {
    pub fn new(raw_html: String) -> Self {
        HTML {
            raw_html,
            unfinished: Vec::new(),
        }
    }

    pub fn parse(&mut self) -> Element {
        let mut text = String::new();
        let mut in_tag = false;
        let html_content: Vec<char> = self.raw_html.chars().collect();

        for c in html_content {
            if c == '<' {
                in_tag = true;
                
                if (self.unfinished.is_empty() || self.unfinished.last().unwrap().tag != "style") && !text.is_empty() {
                    self.add_text(&text);
                }

                text.clear();
            } else if c == '>' {
                in_tag = false;
                self.add_tag(&text);
                text.clear();
            } else {
                text.push(c);
            }
        }
        
        if !in_tag && !text.is_empty() {
            self.add_text(&text);
        }

        self.finish()
    }

    fn add_text(&mut self, text: &str) {
        let trimmed = text.trim();
        if trimmed.is_empty() {
            return;
        }

        self.implicit_tags(None);
        
        if let Some(parent) = self.unfinished.last_mut() {
            let node = Node::Text(Text {
                text: text.to_string(),
                parent: Some(Box::new(Node::Element(parent.clone()))),
                children: Vec::new()
            });
            parent.children.push(node);
        }
    }

    fn get_attributes(&self, text: &str) -> (String, HashMap<String, String>) {
        let parts: Vec<&str> = text.split_whitespace().collect();
        if parts.is_empty() {
            return (String::new(), HashMap::new());
        }

        let tag = parts[0].to_lowercase();
        let mut attributes: HashMap<String, String> = HashMap::new();
        
        for attrpair in &parts[1..] {
            if attrpair.contains('=') {
                let mut split = attrpair.splitn(2, '=');
                let key = split.next().unwrap_or("");
                let mut value = split.next().unwrap_or("");
                
                if value.len() > 2 && (value.starts_with('\'') || value.starts_with('"')) {
                    value = &value[1..value.len() - 1];
                }

                attributes.insert(key.to_lowercase(), value.to_string());
            } else {
                attributes.insert(attrpair.to_lowercase(), String::new());
            }
        }

        (tag, attributes)
    }

    fn add_tag(&mut self, tag: &str) {
        let (tag_name, attributes) = self.get_attributes(tag);
        
        if tag_name.starts_with('!') {
            return;
        }

        self.implicit_tags(Some(&tag_name));

        if tag_name.starts_with('/') {
            if self.unfinished.len() == 1 {
                return;
            }

            let node = self.unfinished.pop().unwrap();
            if let Some(parent) = self.unfinished.last_mut() {
                parent.children.push(Node::Element(node));
            }
        } else if SELF_CLOSING_TAGS.contains(&tag_name.as_str()) {
            let parent_node = self.unfinished.last().map(|p| Box::new(Node::Element(p.clone())));
            if let Some(parent) = self.unfinished.last_mut() {
                let node = Element {
                    tag: tag_name,
                    attributes,
                    children: Vec::new(),
                    parent: parent_node,
                };
                parent.children.push(Node::Element(node));
            }
        } else {
            let node = Element {
                tag: tag_name,
                attributes,
                children: Vec::new(),
                parent: self.unfinished.last().map(|p| Box::new(Node::Element(p.clone()))),
            };
            
            self.unfinished.push(node);
        }
    }

    fn implicit_tags(&mut self, tag: Option<&str>) {
        loop {
            let open_tags: Vec<String> = self.unfinished.iter().map(|node| node.tag.clone()).collect();

            if open_tags.is_empty() && tag != Some("html") {
                self.add_tag("html");
            } else if open_tags == vec!["html"] && !matches!(tag, Some("head") | Some("body") | Some("/html")) {
                if let Some(tag_str) = tag {
                    if HEAD_TAGS.contains(&tag_str) {
                        self.add_tag("head");
                    } else {
                        self.add_tag("body");
                    }
                } else {
                    self.add_tag("body");
                }
            } else if open_tags == vec!["html", "head"] && !matches!(tag, Some(t) if HEAD_TAGS_EXTRA.contains(&t)) {
                self.add_tag("/head");
            } else {
                break;
            }
        }
    }

    fn finish(&mut self) -> Element {
        if self.unfinished.is_empty() {
            self.implicit_tags(None);
        }
    
        while self.unfinished.len() > 1 {
            let node = self.unfinished.pop().unwrap();
            if let Some(parent) = self.unfinished.last_mut() {
                parent.children.push(Node::Element(node));
            }
        }

        self.unfinished.pop().unwrap()
    }
}

pub struct TagSelector {
    pub tag: String,
    pub priority: i32
}

impl TagSelector {
    pub fn matches(&self, node: &Node) -> bool{
        if let Node::Element(elem) = node {
            self.tag == elem.tag
        } else {
            false
        }
    }

    pub fn new(tag: String) -> TagSelector {
        TagSelector {
            tag,
            priority: 1
        }
    }
}
    
pub struct DescendantSelector {
    pub ancestor: Box<Rule>,
    pub descendant: Box<Rule>,
    pub priority: i32
}

impl DescendantSelector {
    pub fn new(ancestor: Rule, descendant: Rule) -> DescendantSelector {
        let new_priority = ancestor.priority() + descendant.priority();
        DescendantSelector {
            ancestor: Box::new(ancestor),
            descendant: Box::new(descendant),
            priority: new_priority
        }
    }

    pub fn matches(&self, node: &Node) -> bool {
        if !self.descendant.matches(node) {
            return false;
        }

        let mut current = node;

        loop {
            match current.parent() {
                Some(parent) => {
                    if self.ancestor.matches(parent) {
                        return true;
                    } 

                    current = parent;
                },
                None => break
            }
        }

        return false;
    }   
}

pub enum Rule {
    TagSelector(TagSelector),
    DescendantSelector(DescendantSelector),
}

impl Rule {
    pub fn priority(&self) -> i32 {
        match self {
            Rule::TagSelector(s) => s.priority,
            Rule::DescendantSelector(s) => s.priority,
        }
    }
    pub fn matches(&self, node: &Node) -> bool {
        match self {
            Rule::TagSelector(s) => s.matches(node),
            Rule::DescendantSelector(s) => s.matches(node),
        }
    }
}

pub fn cascade_priority(rule: (Rule, HashMap<String, String>)) -> i32 {
    rule.0.priority()
}

pub fn get_inline_styles(node: &Node) -> Vec<(Rule, HashMap<String, String>)> {
    let mut all_rules = vec![];

    if let Node::Element(elem) = node {
        for child in &elem.children {
            if let Node::Element(child_elem) = child {
                if child_elem.tag == "style" {
                    if let Some(Node::Text(text_node)) = child_elem.children.first() {
                        all_rules.extend(CSSParser::new(text_node.text.clone()).parse());
                    }
                }
            }
            all_rules.extend(get_inline_styles(child));
        }
    }

    all_rules
}

pub struct CSSParser {
    chars: Vec<char>,
    len: usize,
    i: usize
}

impl CSSParser {
    fn new (s: String) -> CSSParser {
        CSSParser {
            chars: s.chars().collect(),
            len: s.chars().count(),
            i: 0
        }
    }
    
    fn whitespace(&mut self) {
        while self.i < self.len && self.chars[self.i].is_whitespace() {
            self.i += 1;
        }
    }
        
    fn literal(&mut self, literal: char) -> Result<(), String> {
        if !(self.i < self.len && self.chars[self.i] == literal) {
            return Err(format!("Expected '{}'", literal));
        }

        self.i += 1;
        
        Ok(())
    }

    fn word(&mut self) -> Result<String, String> {
        let start = self.i;
        
        while self.i < self.len {
            if self.chars[self.i].is_alphanumeric() || "#-.%".contains(self.chars[self.i]) {
                self.i += 1;
            }

            else {
                break
            }
        }

        if !(self.i > start) {
            return Err("Parsing error: unexpected word".to_string())
        };

        Ok(self.chars[start..self.i].iter().collect())
    }
        
    fn pair(&mut self) -> Result<(String, String), String> {
        let prop = self.word()?;
        
        self.whitespace();
        self.literal(':')?;
        self.whitespace();
        
        let val = self.word()?;

        Ok((prop.to_lowercase(), val))
    }

    fn ignore_until(&mut self, chars: Vec<char>) -> Option<char> {
        while self.i < self.len {
            let c = self.chars[self.i];
            if chars.contains(&c) {
                return Some(c);
            }
            else {
                self.i += 1;
            }
        }

        return None;
    }

    fn body(&mut self) -> HashMap<String, String> {
        let mut pairs = HashMap::new();

        while self.i < self.len && self.chars[self.i] != '}' {
            match self.pair() {
                Ok((prop, val)) => {
                    pairs.insert(prop, val);
                    self.whitespace();
                    let _ = self.literal(';');
                    self.whitespace();
                }
                Err(_) => {
                    let ignore_char: Vec<char> = vec![';', '}'];
                    if let Some(';') = self.ignore_until(ignore_char) {
                        let _ = self.literal(';');
                        self.whitespace();
                    } else {
                        break;
                    }
                }
            }
        }

        pairs
    }
    
    fn selector(&mut self) -> Result<Rule, String> {
        let mut out = Rule::TagSelector(TagSelector::new(self.word()?.to_lowercase()));
        
        self.whitespace();
        
        while self.i < self.len && self.chars[self.i] != '{' {
            let tag = self.word()?;
            let descendant = Rule::TagSelector(TagSelector::new(tag.to_lowercase()));
            out = Rule::DescendantSelector(DescendantSelector::new(out, descendant));
            self.whitespace();
        }
        
        Ok(out)
    }

    pub fn parse(&mut self) -> Vec<(Rule, HashMap<String, String>)> {
        let mut rules = vec![];
        while self.i < self.len {
            self.whitespace();
            
            let selector = match self.selector() {
                Ok(s) => s,
                Err(_) => {
                    if let Some('}') = self.ignore_until(vec!['}']) {
                        let _ = self.literal('}');
                        self.whitespace();
                    } else {
                        break;
                    }
                    continue;
                }
            };
            
            if self.literal('{').is_err() {
                if let Some('}') = self.ignore_until(vec!['}']) {
                    let _ = self.literal('}');
                    self.whitespace();
                } else {
                    break;
                }
                continue;
            };
            
            self.whitespace();
            
            let body = self.body();
            
            let _ = self.literal('}');

            rules.push((selector, body));
        
        }

        return rules;
    }

}
