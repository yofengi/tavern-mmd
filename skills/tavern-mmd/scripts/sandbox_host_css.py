"""Conservative host-CSS subset shared by SBK and offline preview.

This is not a copy of the platform sanitizer. Unsupported syntax is diagnosed,
not silently accepted as platform-compatible. Ordinary sandbox CSS stays local.
"""
import json
import re
from pathlib import Path


def load_host_contract():
    path = Path(__file__).resolve().parent / 'fixtures/mmdsandbox/host-contract.json'
    return json.loads(path.read_text(encoding='utf-8'))


def _uncomment(text):
    out, i, quote = [], 0, ''
    while i < len(text):
        ch = text[i]
        if quote:
            out.append(ch)
            if ch == '\\' and i + 1 < len(text):
                i += 1
                out.append(text[i])
            elif ch == quote:
                quote = ''
        elif ch in '\"\'':
            quote = ch
            out.append(ch)
        elif text.startswith('/*', i):
            end = text.find('*/', i + 2)
            if end < 0:
                raise ValueError('未闭合 CSS 注释')
            i = end + 1
        else:
            out.append(ch)
        i += 1
    if quote:
        raise ValueError('未闭合 CSS 字符串')
    return ''.join(out)


def _positions(text, wanted):
    """Yield delimiters outside strings, parentheses and attribute selectors."""
    quote, escaped, stack = '', False, []
    for i, ch in enumerate(text):
        if escaped:
            escaped = False
            continue
        if ch == '\\':
            escaped = True
            continue
        if quote:
            if ch == quote:
                quote = ''
            continue
        if ch in '\"\'':
            quote = ch
        elif ch in '([':
            stack.append(ch)
        elif ch in ')]':
            if not stack or stack.pop() != ( '(' if ch == ')' else '[' ):
                raise ValueError('不匹配的 CSS 括号')
        elif not stack and ch in wanted:
            yield i, ch
    if quote or stack or escaped:
        raise ValueError('未闭合 CSS 字符串或括号')


def _split(text, delimiter):
    last = 0
    for i, _ in _positions(text, delimiter):
        yield text[last:i]
        last = i + 1
    yield text[last:]


def _rules(text):
    start, opening, depth = 0, None, 0
    for i, ch in _positions(text, '{};'):
        if ch == '{':
            if depth == 0:
                opening = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth < 0:
                raise ValueError('多余的 CSS 闭合花括号')
            if depth == 0:
                yield text[start:opening].strip(), text[opening + 1:i], text[start:i + 1]
                start, opening = i + 1, None
        elif depth == 0:
            yield text[start:i + 1].strip(), None, text[start:i + 1]
            start = i + 1
    if depth or text[start:].strip():
        raise ValueError('不完整的 CSS 规则')


_ROOT = re.compile(r'^\[data-host\s*=\s*(?:"([a-z-]+)"|\'([a-z-]+)\'|([a-z-]+))\]')
_BAD_VALUE = re.compile(r'url\s*\(|expression\s*\(|javascript\s*:|@import', re.I)


def _mentions_host(text):
    """Detect attribute selectors, not quoted declaration values or text."""
    quote, escaped = '', False
    for i, ch in enumerate(text):
        if escaped:
            escaped = False
        elif ch == '\\':
            escaped = True
        elif quote:
            if ch == quote:
                quote = ''
        elif ch in '\"\'':
            quote = ch
        elif ch == '[' and re.match(r'\[\s*data-host(?:\s|[~|^$*]?=|\])', text[i:], re.I):
            return True
    return False


def extract_host_css(css):
    """Return {css, sandbox_css, rules, roots, diagnostics}; never forward scripts.

    Host builders should reject diagnostics or non-empty sandbox_css. Preview
    can show the supported remainder and report dropped input to the author.
    """
    result = dict(css='', sandbox_css='', rules=[], roots=[], diagnostics=[])
    allowed = load_host_contract()['roots']

    def diag(code, message):
        result['diagnostics'].append(dict(code=code, message=message))

    def process(text):
        host, local = [], []
        for head, body, raw in _rules(text):
            has_host = _mentions_host(raw)
            if not has_host:
                local.append(raw)
                continue
            if '\\' in head or '<' in raw:
                diag('unsupported-syntax', '宿主 CSS 不接受转义选择器或 HTML 标记')
                continue
            if head.startswith('@'):
                if body is not None and re.match(r'^@media(?:\s+|(?=\())[^{};\\]+$', head, re.I) and not _BAD_VALUE.search(head):
                    nested, remaining = process(body)
                    host.extend(head + '{' + block + '}' for block in nested)
                    if remaining:
                        local.append(head + '{' + ''.join(remaining) + '}')
                else:
                    diag('unsupported-at-rule', '宿主预览仅模拟 @media；其他 at-rule 需平台验证')
                continue
            selectors = [s.strip() for s in _split(head, ',')]
            names, valid = [], True
            for selector in selectors:
                match = _ROOT.match(selector)
                name = next((g for g in match.groups() if g), '') if match else ''
                tail = selector[match.end():] if match else selector
                if not match or name not in allowed:
                    diag('host-root', '选择器必须最左使用开放的精确 data-host 根：' + selector)
                    valid = False
                elif tail and (not (tail[0].isspace() or tail[0] == '>') or tail.lstrip().startswith(('+', '~', '|'))):
                    diag('host-scope', '宿主根后仅支持后代关系，不能选择树外兄弟：' + selector)
                    valid = False
                elif re.search(r':(?:has|is|where)\s*\(', selector, re.I) or '&' in selector:
                    diag('unsupported-selector', '宿主复杂选择器未模拟，:has 在测试站曾被过滤：' + selector)
                    valid = False
                else:
                    names.append(name)
            if not valid or body is None:
                continue
            if any(True for _ in _positions(body, '{}')):
                diag('nested-css', '宿主原生嵌套规则整条丢弃，请平铺')
                continue
            declarations = []
            for declaration in _split(body, ';'):
                if not declaration.strip():
                    continue
                prop, colon, value = declaration.partition(':')
                prop, value = prop.strip(), value.strip()
                if not colon or not re.fullmatch(r'(?:--)?[a-zA-Z_-][a-zA-Z0-9_-]*', prop) or not value:
                    diag('declaration', '不支持的 CSS 声明：' + declaration.strip())
                elif '\\' in value or _BAD_VALUE.search(value) or prop.lower() in ('content', 'behavior', '-moz-binding'):
                    diag('filtered-declaration', '宿主声明被保守过滤：' + prop)
                else:
                    declarations.append(prop + ': ' + value + ';')
            if declarations:
                host.append(', '.join(selectors) + ' {' + ' '.join(declarations) + '}')
                for name in names:
                    if name not in result['roots']:
                        result['roots'].append(name)
        return host, local

    try:
        source = _uncomment(str(css))
        if not _mentions_host(source):
            result['sandbox_css'] = str(css)
            return result
        host, local = process(source)
        result.update(css='\n'.join(host), sandbox_css='\n'.join(local), rules=host)
    except ValueError as exc:
        # Invalid structure cannot be split reliably; don't inject any of it.
        result['roots'] = []
        diag('malformed-css', str(exc))
    return result
