"""FLAT (Module 2.7) - Step 1: regular expression text -> postfix token list.

Supported syntax : literals, concatenation, |  *  +  ?  ( )  [a-z0-9] classes
                   and \\x escapes (an escaped character is always a literal).
Not supported    : . ^ $ { } and negated classes (raise RegexError).

The classic pipeline is used:
    tokenize -> insert explicit concatenation -> shunting-yard -> postfix
"""
from dataclasses import dataclass

CHAR, ALT, STAR, PLUS, OPT, LP, RP, CAT, EPS = (
    "CHAR", "ALT", "STAR", "PLUS", "OPT", "LP", "RP", "CAT", "EPS")

UNARY = (STAR, PLUS, OPT)
ENDS_OPERAND = (CHAR, RP, STAR, PLUS, OPT)      # token may end an operand
STARTS_OPERAND = (CHAR, LP)                      # token may start an operand
PRECEDENCE = {ALT: 1, CAT: 2}


class RegexError(ValueError):
    """Raised for malformed or unsupported regular expressions."""


@dataclass(frozen=True)
class Token:
    kind: str
    value: str = ""

    def __str__(self):
        return self.value if self.kind == CHAR else {
            ALT: "|", STAR: "*", PLUS: "+", OPT: "?", LP: "(", RP: ")",
            CAT: ".", EPS: "eps"}[self.kind]


def tokenize(pattern: str):
    toks, i, n = [], 0, len(pattern)
    simple = {"|": ALT, "*": STAR, "+": PLUS, "?": OPT, "(": LP, ")": RP}
    while i < n:
        c = pattern[i]
        if c == "\\":
            if i + 1 >= n:
                raise RegexError("dangling backslash at end of pattern")
            toks.append(Token(CHAR, pattern[i + 1]))
            i += 2
        elif c in simple:
            toks.append(Token(simple[c]))
            i += 1
        elif c == "[":
            j, chars = i + 1, []
            if j < n and pattern[j] == "^":
                raise RegexError("negated character classes are not supported")
            while j < n and pattern[j] != "]":
                ch = pattern[j]
                if ch == "\\" and j + 1 < n:
                    j += 1
                    ch = pattern[j]
                if j + 2 < n and pattern[j + 1] == "-" and pattern[j + 2] != "]":
                    hi = pattern[j + 2]
                    if ord(hi) < ord(ch):
                        raise RegexError(f"bad range {ch}-{hi}")
                    chars.extend(chr(o) for o in range(ord(ch), ord(hi) + 1))
                    j += 3
                else:
                    chars.append(ch)
                    j += 1
            if j >= n:
                raise RegexError("unterminated character class '['")
            chars = list(dict.fromkeys(chars))
            if not chars:
                raise RegexError("empty character class")
            toks.append(Token(LP))
            for k, ch in enumerate(chars):
                if k:
                    toks.append(Token(ALT))
                toks.append(Token(CHAR, ch))
            toks.append(Token(RP))
            i = j + 1
        elif c in ".^${}":
            raise RegexError(f"unsupported metacharacter {c!r} (use a [..] class or \\{c})")
        else:
            toks.append(Token(CHAR, c))
            i += 1
    return toks


def add_concatenation(tokens):
    """Validate operator placement and insert explicit CAT tokens."""
    if not tokens:
        return [Token(EPS)]
    out, prev = [], None
    for idx, t in enumerate(tokens):
        nxt = tokens[idx + 1] if idx + 1 < len(tokens) else None
        if t.kind in UNARY and (prev is None or prev.kind not in ENDS_OPERAND):
            raise RegexError(f"quantifier '{t}' has nothing to repeat")
        if t.kind == ALT:
            if prev is None or prev.kind not in ENDS_OPERAND or nxt is None \
                    or nxt.kind not in STARTS_OPERAND:
                raise RegexError("'|' needs an expression on both sides")
        if t.kind == RP and prev is not None and prev.kind == LP:
            raise RegexError("empty group '()'")
        if prev is not None and prev.kind in ENDS_OPERAND and t.kind in STARTS_OPERAND:
            out.append(Token(CAT))
        out.append(t)
        prev = t
    return out


def to_postfix(tokens):
    """Shunting-yard. Postfix unary operators go straight to the output."""
    out, ops = [], []
    for t in add_concatenation(tokens):
        if t.kind in (CHAR, EPS) or t.kind in UNARY:
            out.append(t)
        elif t.kind == LP:
            ops.append(t)
        elif t.kind == RP:
            while ops and ops[-1].kind != LP:
                out.append(ops.pop())
            if not ops:
                raise RegexError("unbalanced ')'")
            ops.pop()
        else:  # ALT or CAT (left associative)
            while ops and ops[-1].kind != LP and PRECEDENCE[ops[-1].kind] >= PRECEDENCE[t.kind]:
                out.append(ops.pop())
            ops.append(t)
    while ops:
        if ops[-1].kind == LP:
            raise RegexError("unbalanced '('")
        out.append(ops.pop())
    return out


def parse(pattern: str):
    """Pattern text -> postfix token list."""
    return to_postfix(tokenize(pattern))


def postfix_string(postfix) -> str:
    return " ".join(str(t) for t in postfix)
