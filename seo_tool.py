import streamlit as st
import openai
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# --- CONFIGURATION ---
SITEMAP_URL = "https://hireoverseas.com/sitemap.xml" 

# Set page layout
st.set_page_config(page_title="Hire Overseas SEO Suite", layout="wide")

# --- FUNCTIONS ---

def get_sitemap_links(sitemap_url):
    try:
        response = requests.get(sitemap_url, timeout=10)
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            urls = []
            for child in root:
                for sub in child:
                    if 'loc' in sub.tag:
                        urls.append(sub.text)
            return urls[:500] 
    except Exception as e:
        return []
    return []

def scrape_text_from_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for script in soup(["script", "style", "nav", "footer"]):
            script.extract()
        text = soup.get_text(separator=' ')
        
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text[:3000] # Increased limit slightly for comparison
    except Exception as e:
        return f"Could not scrape {url}: {e}"

# --- LOGIC: MODE 1 (NEW CONTENT) ---
def generate_new_content(api_key, primary_kw, secondary_kws, competitor_urls):
    client = openai.OpenAI(api_key=api_key)
    system_instruction = "You are a creative SEO expert. Focus on US Business audience. Write content that converts."
    status = st.empty()
    
    # Phase 1: Keywords
    status.info("Phase 1: Keyword Expansion...")
    kw_prompt = f"Target: {primary_kw}. Secondary: {secondary_kws}. Return ONLY a comma-separated list of top 15 vital keywords (semantic + provided)."
    kw_response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": kw_prompt}])
    final_keywords = kw_response.choices[0].message.content
    
    # Phase 2: Outline
    status.info("Phase 2: Analyzing Competitors & Outlining...")
    competitor_data = ""
    for url in competitor_urls:
        if url:
            content = scrape_text_from_url(url)
            competitor_data += f"\n--- Content from {url} ---\n{content}\n"
            
    analysis_prompt = f"Keywords: {final_keywords}. Competitor Content: {competitor_data}. Create the BEST SEO-optimized outline for '{primary_kw}'."
    outline_response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": analysis_prompt}])
    outline = outline_response.choices[0].message.content

    # Phase 3: Writing
    status.info("Phase 3: Writing Article...")
    writing_prompt = f"""
    Write a unique, SEO-optimized blog post for '{primary_kw}'.
    Outline: {outline}
    Keywords: {final_keywords}
    
    Strict Guidelines:
    - Concise, clear, direct sentences.
    - NO em-dashes ("—"). Use "but", "and", "or" connectors.
    - Focus on unique, purposeful info relevant to US businesses.
    """
    article_response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": writing_prompt}])
    article_content = article_response.choices[0].message.content

    # Phase 4 & 5
    status.info("Phase 4 & 5: Meta Data & Links...")
    meta_prompt = "Create Title (max 60 chars) and Meta Description (max 155 chars) for this article."
    meta_response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": meta_prompt}])
    
    sitemap_links = get_sitemap_links(SITEMAP_URL)
    links_context = "\n".join(sitemap_links) if sitemap_links else "No sitemap data."
    link_prompt = f"Article: {primary_kw}. Site URLs: {links_context}. Suggest 3-5 internal links (Anchor Text -> URL). Use ONLY provided URLs."
    link_response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": link_prompt}])
    
    status.success("Done!")
    return final_keywords, outline, article_content, meta_response.choices[0].message.content, link_response.choices[0].message.content

# --- LOGIC: MODE 2 (CONTENT AUDIT) ---
def audit_existing_content(api_key, target_kw, my_url, competitor_url):
    client = openai.OpenAI(api_key=api_key)
    system_instruction = "You are a ruthless SEO editor. Your job is to find why the competitor is ranking higher and fix it."
    status = st.empty()
    
    status.info("Scraping content...")
    my_content = scrape_text_from_url(my_url)
    comp_content = scrape_text_from_url(competitor_url)
    
    # Phase 1: Gap Analysis
    status.info("Analyzing Content Gaps...")
    audit_prompt = f"""
    Target Keyword: {target_kw}
    
    MY CONTENT:
    {my_content}
    
    COMPETITOR CONTENT (Ranking #1):
    {comp_content}
    
    Compare these two articles. 
    1. Identify 3-5 specific topics, data points, or angles the Competitor covers that I missed.
    2. Analyze the depth difference.
    3. List the missing semantic keywords.
    """
    audit_response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": audit_prompt}])
    audit_result = audit_response.choices[0].message.content
    
    # Phase 2: The Fix
    status.info("Drafting the updates...")
    fix_prompt = f"""
    Based on the audit below, write 3 new sections (paragraphs) that I should insert into my article to close the gap.
    
    Audit Findings:
    {audit_result}
    
    Writing Guidelines:
    - Match the tone of US Business professional.
    - Concise, clear sentences. No em-dashes.
    - Provide "Insert this section after..." instructions.
    """
    fix_response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": fix_prompt}])
    fix_result = fix_response.choices[0].message.content
    
    status.success("Audit Complete!")
    return audit_result, fix_result


# --- FRONTEND UI ---

st.title("🚀 Hire Overseas SEO Suite")

with st.sidebar:
    st.header("Select Tool")
    # THE MODE SWITCHER
    app_mode = st.radio("Choose a Workflow:", ["1. New Article Generator", "2. Content Refresh Auditor"])
    
    st.divider()
    if "OPENAI_API_KEY" in st.secrets:
        st.success("API Key loaded ✅")
        api_key = st.secrets["OPENAI_API_KEY"]
    else:
        api_key = st.text_input("OpenAI API Key", type="password")

# --- UI FOR MODE 1: NEW ARTICLE ---
if app_mode == "1. New Article Generator":
    st.subheader("📝 Generate New Content")
    col1, col2 = st.columns(2)
    with col1:
        primary_kw = st.text_input("Target Keyword")
        secondary_kws = st.text_area("Secondary Keywords List")
    with col2:
        comp_1 = st.text_input("Competitor URL 1")
        comp_2 = st.text_input("Competitor URL 2")
        comp_3 = st.text_input("Competitor URL 3")

    if st.button("Generate Strategy"):
        if not api_key: st.error("Missing API Key")
        elif not primary_kw: st.error("Enter a keyword")
        else:
            competitors = [url for url in [comp_1, comp_2, comp_3] if url]
            kw, out, art, meta, links = generate_new_content(api_key, primary_kw, secondary_kws, competitors)
            
            st.divider()
            st.subheader("Target Keywords")
            st.info(kw)
            with st.expander("View Outline"):
                st.write(out)
            st.subheader("Article Draft")
            st.markdown(art)
            st.download_button("Download", art, f"{primary_kw}_article.md")
            st.subheader("Meta & Links")
            st.code(meta)
            st.warning(links)

# --- UI FOR MODE 2: CONTENT AUDIT ---
elif app_mode == "2. Content Refresh Auditor":
    st.subheader("🔍 Audit & Fix Old Content")
    st.markdown("Compare your old page against the current #1 ranking competitor to find content gaps.")
    
    col1, col2 = st.columns(2)
    with col1:
        my_url = st.text_input("Your Existing URL (The one to fix)")
        target_kw = st.text_input("Target Keyword")
    with col2:
        comp_url = st.text_input("Winning Competitor URL (The standard)")
        
    if st.button("Run Audit"):
        if not api_key: st.error("Missing API Key")
        elif not my_url or not comp_url: st.error("Please enter both URLs")
        else:
            audit, fixes = audit_existing_content(api_key, target_kw, my_url, comp_url)
            
            st.divider()
            st.subheader("1. The Gap Analysis")
            st.info("Here is what the competitor is doing better:")
            st.markdown(audit)
            
            st.divider()
            st.subheader("2. The Fix (Copy-Paste Updates)")
            st.success("Here is the content you need to add to your page:")
            st.markdown(fixes)
