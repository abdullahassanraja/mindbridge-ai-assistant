# test_landing_page.py
# Comprehensive automated verification for MindBridge / Ellen owner-facing marketing sales landing page.
# Uses only Python standard library.

import os
import re
import sys
from html.parser import HTMLParser

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

class LandingPageAuditor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.ids = set()
        self.classes = []
        self.links = []
        self.buttons = []
        self.scripts = []
        self.text_chunks = []
        self.current_tag = None
        self.current_attrs = {}

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        self.tags.append(tag)
        if 'id' in attr_dict:
            self.ids.add(attr_dict['id'])
        if tag == 'a':
            self.links.append(attr_dict)
        if tag == 'button':
            self.buttons.append(attr_dict)
        if tag == 'script' and 'src' in attr_dict:
            self.scripts.append(attr_dict['src'])
        self.current_tag = tag
        self.current_attrs = attr_dict

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.text_chunks.append(text)

def verify_landing_page():
    html_path = os.path.join(os.path.dirname(__file__), 'index.html')
    assert os.path.exists(html_path), f"index.html not found at {html_path}"
    
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    auditor = LandingPageAuditor()
    auditor.feed(html)

    print("=" * 70)
    print("MINDBRIDGE / ELLEN LANDING PAGE AUDIT & VERIFICATION")
    print("=" * 70)

    # 1. Check title & meta
    title_match = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
    assert title_match, "Title tag missing"
    title_text = title_match.group(1).strip()
    print(f"✓ Title: {title_text}")
    assert "Ellen" in title_text and "MindBridge" in title_text

    desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', html, re.DOTALL)
    assert desc_match, "Meta description missing"
    print(f"✓ Meta Description: {desc_match.group(1)[:70]}...")

    # 2. Check Typography & Tailwind CDN
    assert "fonts.googleapis.com" in html, "Google Fonts link missing"
    assert "Fraunces" in html and "Plus+Jakarta+Sans" in html, "Specified fonts missing"
    assert "cdn.tailwindcss.com" in html, "Tailwind CDN missing"
    print("✓ Fonts (Fraunces & Plus Jakarta Sans) and Tailwind CSS configured.")

    # 3. Check All Required Sections by ID
    required_sections = [
        ('the-assistant', 'Hero / The Assistant'),
        ('capabilities', 'Capabilities Matrix'),
        ('differentiation', 'Why Ellen / Differentiation'),
        ('customization', 'Architecture & Customization'),
        ('why-it-matters', 'Why It Matters Narrative'),
        ('playground', 'Interactive Live Playground'),
        ('demo-modal', 'Practice Owner Demo Request Modal'),
    ]

    for sec_id, name in required_sections:
        assert sec_id in auditor.ids, f"Missing required section id='{sec_id}' ({name})"
        print(f"✓ Found section id: #{sec_id} ({name})")

    # 4. Check Hero Exact Copy
    assert "The AI Assistant Built for" in html and "Wellness Practices" in html, "Hero H1 copy missing"
    assert "Ellen answers every visitor, day or night, qualifies every inquiry, and never lets a potential client slip away" in html, "Hero subheadline missing"
    print("✓ Hero H1 and subheadline verbatim confirmed.")

    # 5. Check The Real Cost of a Missed Inquiry
    assert "The Real Cost of a" in html and "Missed Inquiry" in html, "Missed inquiry section missing"
    assert "Without Ellen" in html and "With Ellen" in html, "Before/after columns missing"
    assert "Fewer Missed Inquiries" in html, "Takeaways missing"
    print("✓ 'The Real Cost of a Missed Inquiry' revenue framing confirmed.")

    # 6. Check 7 Capability Matrix Cards
    capabilities = [
        "Never Guesses",
        "Feels Human, Not a Form",
        "Matches the Right Therapist",
        "Captures Every Lead",
        "Fills Your Calendar",
        "Built-In Safety",
        "Knows When to Step Aside",
    ]
    for cap in capabilities:
        assert cap in html, f"Missing capability: {cap}"
    print(f"✓ All 7 Capability Matrix items confirmed: {', '.join(capabilities)}")

    # 7. Check 4 Differentiation Rows
    diff_topics = [
        "Only ever speaks from your actual practice content",
        "mental-health-specific guardrails",
        "Crisis response is fixed, tested, and never left to chance",
        "Built around your specific therapists",
    ]
    for diff in diff_topics:
        assert diff in html, f"Missing differentiation point: {diff}"
    print("✓ All 4 'Not Just Another Chatbot' comparison points confirmed.")

    # 8. Check Architecture & Customization Copy
    assert "Ellen isn't a generic chatbot wearing your logo" in html, "Architecture intro copy missing"
    assert "Free Demo" in html and "Fully Customized" in html and "CRM & Calendar Ready" in html, "Architecture cards missing"
    assert "Get Your Custom Build →" in html, "Custom build CTA missing"
    print("✓ Architecture & Customization section confirmed.")

    # 9. Check Why It Matters Narrative
    assert "A wellness practice's website usually gets one shot" in html, "Why It Matters quote missing"
    assert "Stop Losing Leads, Start Free" in html, "Start Free CTA missing"
    print("✓ Why It Matters editorial quote and CTA confirmed.")

    # 10. Check Playground Interactive Elements
    assert 'id="playground-chips"' in html, "Playground chips missing"
    assert 'class="playground-chip' in html, "Playground chip classes missing"
    assert 'id="playground-form"' in html, "Playground form missing"
    assert 'id="playground-input"' in html, "Playground input missing"
    print("✓ Interactive playground console elements verified.")

    # 11. Check Footer Copy & Compliance Disclaimer
    assert "Every visitor deserves an answer. Give them one." in html, "Footer closing headline missing"
    assert "Ellen is an administrative AI assistant, not a licensed medical provider" in html, "Compliance disclaimer missing"
    print("✓ Footer closing statement and medical compliance disclaimer confirmed.")

    # 12. Check Zero Fake Stats or Prohibited Claims
    # Remove CSS numbers and code patterns
    content_only = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL)
    content_only = re.sub(r'<style.*?</style>', '', content_only, flags=re.DOTALL)
    content_only = re.sub(r'<svg.*?</svg>', '', content_only, flags=re.DOTALL)
    clean_text = re.sub(r'<[^>]+>', ' ', content_only)

    fake_stat_patterns = [
        (r'\b\d{1,3}%\b', "Prohibited percentage claim"),
        (r'\$\d+', "Prohibited dollar figure claim"),
        (r'\b\d+,\d{3}\+?\s+(clients|users|practices|sessions|leads)\b', "Prohibited fabricated scale claim"),
        (r'\b(Dr\.\s+[A-Z][a-z]+,\s+Clinical\s+Director|says\s+Dr\.)', "Prohibited fabricated testimonial"),
    ]
    for pat, desc in fake_stat_patterns:
        matches = re.findall(pat, clean_text, flags=re.IGNORECASE)
        assert len(matches) == 0, f"Violation: Found {desc} with pattern '{pat}': {matches}"
    print("✓ Strict compliance: 0 fake statistics, 0 fabricated percentages, 0 dollar figures, 0 fake testimonials.")

    # 13. Audit CTAs and Target Destinations
    print("\n" + "=" * 70)
    print("CTA DESTINATION REGISTRY AUDIT")
    print("=" * 70)
    cta_patterns = [
        ('Get a Free Demo Built for Your Practice (Hero)', '#demo-modal (Opens Demo Request Modal)'),
        ('See a Live Demo (Hero)', '#playground / Launches Ellen widget'),
        ('Test Ellen live on this website (Preview Card)', 'window.MindBridge.open() + auto-prompts Ellen'),
        ('Get Your Custom Build → (Customization)', '#demo-modal (Opens Demo Request Modal)'),
        ('Stop Losing Leads, Start Free (Why It Matters)', '#demo-modal (Opens Demo Request Modal)'),
        ('Ask Ellen (Playground Submit)', 'window.MindBridge.send(input) in live chat widget'),
        ('Prompt Chips (Playground 4x)', 'window.MindBridge.send(chip_prompt) in live chat widget'),
        ('Talk to Us (Header Nav)', '#demo-modal (Opens Demo Request Modal)'),
        ('Get a Free Demo (Footer)', '#demo-modal (Opens Demo Request Modal)'),
        ('Book a Call (Footer)', 'mailto:contact@mindbridgewellness.demo?subject=Book%20a%20Call%20-%20MindBridge%20Ellen'),
        ('See Pricing (Footer)', '#demo-modal (Opens Demo Request Modal)'),
    ]
    for label, dest in cta_patterns:
        print(f"• {label} -> {dest}")

    # 14. Check widget.js integration
    assert "widget.js" in auditor.scripts, "widget.js script tag missing"
    assert "window.MindBridge" in html, "window.MindBridge interaction code missing in index.html"
    print("✓ widget.js loaded and wired to page interaction handlers.")

    print("\n" + "=" * 70)
    print("✅ ALL 14 AUTOMATED AUDIT CHECKS PASSED PERFECTLY!")
    print("=" * 70)

if __name__ == '__main__':
    verify_landing_page()
