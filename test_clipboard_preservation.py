"""
Focused regression test for clipboard restoration and text injection.
Tests:
1. Standard ASCII text
2. Multiline text with CRLF and LF
3. Unicode (emojis, accented characters, CJK characters, math symbols)
4. Empty string and whitespace-only content
5. Code snippets with quotes and indentation
"""
import pyperclip
from engine_injector import insert_text, _safe_copy, _safe_paste

def run_tests():
    test_cases = [
        ("Standard ASCII", "Hello World from OpenFlow"),
        ("Multiline content", "Line 1: OpenFlow\r\nLine 2: Indented text\nLine 3: Trailing newline\n"),
        ("Unicode & Emojis", "Symbols: © ® ™ € £ ¥ 🚀 🎙️ — 日本語, हिन्दी, Español: ¡Olé!"),
        ("Empty string", ""),
        ("Whitespace only", "   \t\n  "),
        ("Code snippet", "def compute(a, b):\n    return a * b + 42\n")
    ]

    print("Running Clipboard Injection & Restoration Tests...\n" + "="*50)
    for label, original in test_cases:
        copied = _safe_copy(original, retries=10, delay=0.05)
        assert copied, f"Failed setting initial clipboard for: {label}"
        dictation = f"Dictated injection for: {label}"

        # Execute insertion
        insert_text(dictation, paste_wait=0.08)

        restored = _safe_paste(retries=10, delay=0.05)
        assert restored == original, f"Failed on [{label}]: expected {repr(original)}, got {repr(restored)}"
        print(f"[OK] [{label}] Passed (length: {len(original)})")

    print("="*50 + "\nAll 6 clipboard preservation tests PASSED successfully!")

if __name__ == "__main__":
    run_tests()
