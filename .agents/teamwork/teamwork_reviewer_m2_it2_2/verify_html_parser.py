from html.parser import HTMLParser

class MyParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.attrs = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.append(dict(attrs))

parser = MyParser()
test_html = '<button class="gen-ui-btn &quot;&gt;&lt;img src=x onerror=alert(3)&gt;" data-action-id="a1"><span>L</span></button>'
parser.feed(test_html)

print("Parsed tags:", parser.tags)
print("Parsed attrs:", parser.attrs)

assert parser.tags == ["button", "span"], f"Unexpected tags parsed: {parser.tags}"
assert parser.attrs[0]["class"] == 'gen-ui-btn "><img src=x onerror=alert(3)>'
print("ALL HTML PARSER TOKENIZATION ASSERTIONS PASSED: No tag breakout occurred!")
