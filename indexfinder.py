import re
import pandas as pd
import os

def extract_toc(text):
    # Normalize and clean
    txt = text.replace('\r\n', '\n')

    # Locate start of TOC
    toc_start_match = re.search(r'(^|\n)\s*(TABLE\s+OF\s*CONTENTS|TABLEOFCONTENTS|Contents|TABLE OFCONTENTS|TABLE OF CONTENTS)\s*(\n|$)', txt, re.IGNORECASE)
    start_idx = toc_start_match.start() if toc_start_match else 0

    # Limit TOC to next 100 lines
    next_100_lines = txt[start_idx:].splitlines()[:100]
    combined_text = '\n'.join(next_100_lines)
    
    # Find approximate end of TOC within these 100 lines
    body_match = re.search(r'\n\n[A-Z][a-z].{20,}', combined_text)
    end_idx = body_match.start() if body_match else len(combined_text)
    toc_region = combined_text[:end_idx]

    lines = [ln.strip() for ln in toc_region.splitlines() if ln.strip()]

    # Pre-process: Join lines that are part of the same entry
    processed_lines = []
    current_line = ""
    
    for i, ln in enumerate(lines):
        # Skip TOC header
        if re.match(r'^(TABLE\s+OF\s*CONTENTS|TABLEOFCONTENTS|Contents|TABLE OFCONTENTS|TABLE OF CONTENTS)$', ln, re.IGNORECASE):
            continue
            
        # If line has dots and number, it's an end of entry
        if re.search(r'\.{2,}\s*\d+\s*$', ln):
            if current_line:
                # Combine with previous line
                processed_lines.append(f"{current_line} {ln}")
                current_line = ""
            else:
                processed_lines.append(ln)
        else:
            # If next line has dots and number, this is a title line
            if i + 1 < len(lines) and re.search(r'\.{2,}\s*\d+\s*$', lines[i + 1]):
                current_line = ln
            else:
                processed_lines.append(ln)

    entries = []
    for ln in processed_lines:
        # skip TOC header line
        if re.match(r'^(TABLE\s+OF\s*CONTENTS|TABLEOFCONTENTS|Contents|TABLE OFCONTENTS|TABLE OF CONTENTS)$', ln, re.IGNORECASE):
            continue

        # First, try to extract simple "title ... page" pattern
        m = re.match(r'^(.*?)[\s\.]+\d+\s*$', ln)
        if m:
            # Split the line by groups of dots
            parts = re.split(r'\.{2,}', ln)
            if parts:
                # First part is the title
                title = parts[0].strip()
                # Find the page number at the end
                page_match = re.search(r'\b(\d+)\s*$', ln)
                if page_match:
                    page = int(page_match.group(1))
                    title = re.sub(r'\bS\s*A\s*M\s*P\s*L\s*E\b', 'SAMPLE', title, flags=re.IGNORECASE)
                    title = re.sub(r'[_]{2,}', ' ', title)
                    title = re.sub(r'\s{2,}', ' ', title)
                    level = 2 if title.lower().startswith('part') else 1
                    entries.append({'title': title, 'page': page, 'raw_line': ln, 'level': level})
                    continue

        # Pattern 2: Standard title ... page number
        m = re.match(r'^(?P<title>.+?)\s*\.{2,}\s*(?P<page>\d+)$', ln)
        if not m:
            m = re.match(r'^(?P<title>.+?)\s+(-|\u2014)?\s*(?P<page>\d+)$', ln)
        if not m:
            m = re.match(r'^(?P<title>.+?)\s+(?P<page>\d{1,3})$', ln)

        if m:
            title = m.group('title').strip()
            page = int(m.group('page'))
            title = re.sub(r'\bS\s*A\s*M\s*P\s*L\s*E\b', 'SAMPLE', title, flags=re.IGNORECASE)
            title = re.sub(r'[_]{2,}', ' ', title)
            title = re.sub(r'\s{2,}', ' ', title)
            level = 2 if title.lower().startswith('part') else 1
            entries.append({'title': title, 'page': page, 'raw_line': ln, 'level': level})
        else:
            m2 = re.search(r'(?P<page>\d{1,3})\s*$', ln)
            if m2:
                page = int(m2.group('page'))
                title = ln[:m2.start()].strip(' .\t_')
                entries.append({'title': title, 'page': page, 'raw_line': ln, 'level': 2 if title.lower().startswith('part') else 1})

    entries.sort(key=lambda x: x['page'])
    return entries


if __name__ == "__main__":
    # List of policy documents to process
    policy_files = [
        "2024_policy_jacket.txt",
        "Allstate.txt",
        "StateFarm.txt",
        "EAI_6080_Final_Project_Proposal_VenkatNeelraj_Nitta.txt",
        "example.txt"
    ]
    
    # Dictionary to store policy texts
    example_texts = {}
    
    # Read all policy files
    for i, filename in enumerate(policy_files, 1):
        filepath = os.path.join("PolicyDocs", filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    example_texts[f"example{i}"] = f.read()
                print(f"✅ Successfully loaded {filename}")
            except Exception as e:
                print(f"❌ Error reading {filename}: {str(e)}")
        else:
            print(f"❌ File not found: {filepath}")

    # Output folder
    outdir = "extracted_toc"
    os.makedirs(outdir, exist_ok=True)

    for name, text in example_texts.items():
        entries = extract_toc(text)
        df = pd.DataFrame(entries)
        outfile = os.path.join(outdir, f"{name}_toc.csv")
        df.to_csv(outfile, index=False)
        print(f"\n✅ Saved {len(df)} entries to {outfile}")
        print(df.head())
