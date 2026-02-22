use std::collections::HashMap;
use std::sync::LazyLock;

// Regex is by AI
// pub const emoji_pattern = re.compile(
//     r'['
//     r'\U0001F300-\U0001F5FF'
//     r'\U0001F600-\U0001F64F'
//     r'\U0001F680-\U0001F6FF'
//     r'\U0001F700-\U0001F77F'
//     r'\U0001F780-\U0001F7FF'
//     r'\U0001F800-\U0001F8FF'
//     r'\U0001F900-\U0001F9FF'
//     r'\U0001FA00-\U0001FA6F'
//     r'\U0001FA70-\U0001FAFF'
//     r'\u2600-\u26FF'
//     r'\u2700-\u27BF'
//     r']',
//     flags=re.UNICODE
// )

// token_pattern = re.compile(
//     f'({emoji_pattern.pattern})'  // emoji
//     r'|(\w+)'                     // word
//     r'|([^\w\s])',                // punctuation
//     flags=re.UNICODE
// )

pub const BLOCK_ELEMENTS: [&str; 37] = [
    "html", "body", "article", "section", "nav", "aside",
    "h1", "h2", "h3", "h4", "h5", "h6", "hgroup", "header",
    "footer", "address", "p", "hr", "pre", "blockquote",
    "ol", "ul", "menu", "li", "dl", "dt", "dd", "figure",
    "figcaption", "main", "div", "table", "form", "fieldset",
    "legend", "details", "summary"
];

pub const SELF_CLOSING_TAGS: [&str; 14] = [
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
];

pub const HEAD_TAGS: [&str; 9] = [
    "base", "basefont", "bgsound", "noscript",
    "link", "meta", "title", "style", "script",
];

pub const HEAD_TAGS_EXTRA: [&str; 10] = [
    "base", "basefont", "bgsound", "noscript",
    "link", "meta", "title", "style", "script", "/head"
];

pub static INHERITED_PROPERTIES: LazyLock<HashMap<String, String>> = LazyLock::new(|| HashMap::from([
    (String::from("font-family"), String::from("Arial")),
    (String::from("font-size"), String::from("16px")),
    (String::from("font-style"), String::from("normal")),
    (String::from("font-weight"), String::from("normal")),
    (String::from("color"), String::from("black")),
    (String::from("display"), String::from("inline")),
    (String::from("width"), String::from("auto")),
    (String::from("height"), String::from("auto"))
]));

pub static DEFAULT_HEADERS: LazyLock<HashMap<String, String>> = LazyLock::new(|| HashMap::from([
    (String::from("User-Agent"), String::from("Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0")),
    (String::from("Accept"), String::from("text/html")),
    (String::from("Sec-Fetch-Dest"), String::from("document")),
    (String::from("Sec-Fetch-Mode"), String::from("navigate")),
    (String::from("Sec-Fetch-Site"), String::from("none"))
]));