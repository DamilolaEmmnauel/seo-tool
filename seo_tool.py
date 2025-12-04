import streamlit as st
import openai
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

# --- CONFIGURATION ---
# Replace this with your ACTUAL sitemap URL for the Hire Overseas website
# Example: "https://hireoverseas.com/sitemap.xml" or "https://hireoverseas.com/post-sitemap.xml"
SITEMAP_URL = "https://hireoverseas.com/sitemap.xml" 

# Set page layout
st.set_page_config(page_title="Hire Overseas SEO Generator", layout="wide")

# --- FUNCTIONS ---

def get_sitemap_links(sitemap_url):
    """Fetches real URLs from the website to prevent hallucination."""
    try:
        response = requests.get(sitemap_url, timeout=10)
        if response.status_code == 200:
            # Parse XML
            root = ET.fromstring(response.content)
            # Extract URLs (handling standard sitemap schemas)
            urls = []
            for child in root:
                for sub in child:
                    if 'loc' in sub.tag:
                        urls.append(sub.text)
            return urls[:500] # Limit to 500 to save tokens/time
    except Exception as e:
        return []
    return []

def scrape_text_from_url(url):
    """Scrapes text from competitor URLs."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # specific logic to get body content, removing scripts/styles
        for script in soup(["script", "style", "nav", "footer"]):
            script.extract()
        text = soup.get_text(separator=' ')
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text[:2000] # Limit characters per competitor to save tokens
    except Exception as e:
        return f"Could not scrape {url}: {e}"

def generate_seo_content(api_key, primary_kw, secondary_kws, competitor_urls):
    client = openai.OpenAI(api_key=api_key)
    
    # SYSTEM PROMPT (The Persona)
    system_instruction = """
    You are a creative SEO expert with content expertise.
    You are going to carry out content creation that will make 'Hire Overseas' a go-to website to hire remote workers.
    Make the content align with US businesses/users looking to hire workers remotely.
    Ensure it is humanly written and aligns with the keyword intent.
    """

    status = st.empty()
    
    # --- STEP 1: KEYWORD PROCESSING ---
    status.info("Phase 1: Analyzing and expanding keywords...")
    kw_prompt = f"""
    Target Primary Keyword: {primary_kw}
    Initial Secondary Keywords: {secondary_kws}
    
    1. Review the secondary keywords.
    2. Generate semantic keywords relevant to the primary keyword.
    3. Return ONLY a comma-separated list of the top 15 most vital keywords (combining the provided ones and your semantic ones).
    """
    
    kw_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": kw_prompt}]
    )
    final_keywords = kw_response.choices[0].message.content
    
    # --- STEP 2: COMPETITOR ANALYSIS ---
    status.info("Phase 2: Scraping and analyzing competitors...")
    competitor_data = ""
    for url in competitor_urls:
        if url:
            content = scrape_text_from_url(url)
            competitor_data += f"\n--- Content from {url} ---\n{content}\n"
            
    analysis_prompt = f"""
    The target keywords are: {final_keywords}
    
    Here is the content from top competitors for the primary keyword '{primary_kw}':
    {competitor_data}
    
    Analyze their content structures, gaps, and strengths. 
    Based on this analysis, create the BEST SEO-optimized outline for a new article.
    """
    
    outline_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": analysis_prompt}]
    )
    outline = outline_response.choices[0].message.content

    # --- STEP 3: WRITING CONTENT ---
    status.info("Phase 3: Writing the article (this may take a minute)...")
    writing_prompt = f"""
    Using the outline below, write the full article.
    
    Outline:
    {outline}
    
    Requirements:
    - Integrate these keywords naturally: {final_keywords}
    - NO Keyword stuffing.
    - Must be human-written, engaging, and professional.
    - Focus on US Business audience.
    """
    
    article_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": writing_prompt}]
    )
    article_content = article_response.choices[0].message.content

    # --- STEP 4: META DATA ---
    status.info("Phase 4: Generating Meta Data...")
    meta_prompt = f"""
    Based on the article written, create:
    1. A Title Tag (Max 60 chars).
    2. A Meta Description (Max 155 chars).
    """
    meta_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": meta_prompt}]
    )
    meta_data = meta_response.choices[0].message.content

    # --- STEP 5: INTERNAL LINKING ---
    status.info("Phase 5: Finding internal linking opportunities...")
    
    # Fetch real sitemap links
    sitemap_links = get_sitemap_links(SITEMAP_URL) 
    
    # If sitemap fetch fails or is empty, we handle it gracefully
    links_context = "\n".join(sitemap_links) if sitemap_links else "No sitemap data found. Suggest general relevant anchors."

    link_prompt = f"""
    The article is about: {primary_kw}
    
    Here is a list of actual URLs found on the hireoverseas.com website:
    {links_context}
    
    Review the article you wrote. Identify 3-5 opportunities to internally link to the URLs provided above.
    List them as: "Anchor Text" -> URL.
    DO NOT fabricate URLs. Only use URLs from the list provided.
    """
    
    link_response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": system_instruction}, {"role": "user", "content": link_prompt}]
    )
    internal_links = link_response.choices[0].message.content
    
    status.success("Done!")
    
    return final_keywords, outline, article_content, meta_data, internal_links

# --- FRONTEND UI ---

st.title("🚀 Hire Overseas SEO Content Generator")
st.markdown("Automated workflow: Keyword Expansion -> Competitor Spy -> Outline -> Write -> Optimize.")

with st.sidebar:
    st.header("Settings")
    
    # --- NEW: SECRETS MANAGEMENT ---
    if "OPENAI_API_KEY" in st.secrets:
        st.success("API Key loaded from Cloud Secrets ✅")
        api_key = st.secrets["OPENAI_API_KEY"]
    else:
        st.warning("No Secrets found (Local Mode).")
        api_key = st.text_input("OpenAI API Key", type="password")
    # -------------------------------

    st.markdown("---")
    st.write("Created for the SEO Team.")

# Form inputs
col1, col2 = st.columns(2)
with col1:
    primary_kw = st.text_input("1. Primary Keyword")
    secondary_kws = st.text_area("2. Secondary Keywords (Paste list)")

with col2:
    comp_1 = st.text_input("Competitor URL 1")
    comp_2 = st.text_input("Competitor URL 2")
    comp_3 = st.text_input("Competitor URL 3")

if st.button("Generate Content Strategy"):
    if not api_key:
        st.error("Missing OpenAI API Key. Please add it to Secrets or the sidebar.")
    elif not primary_kw:
        st.error("Please enter a primary keyword.")
    else:
        competitors = [url for url in [comp_1, comp_2, comp_3] if url]
        
        # Run the logic
        keywords, outline, article, meta, links = generate_seo_content(
            api_key, primary_kw, secondary_kws, competitors
        )
        
        # Display Results
        st.divider()
        st.subheader("1. Target Keywords Strategy")
        st.info(keywords)
        
        st.subheader("2. SEO Outline")
        st.text_area("Outline", outline, height=200)
        
        st.subheader("3. Final Article")
        st.markdown(article)
        st.download_button("Download Article", article, file_name=f"{primary_kw.replace(' ', '_')}_article.md")
        
        st.subheader("4. Meta Data")
        st.code(meta, language='text')
        
        st.subheader("5. Internal Linking Opportunities")
        st.warning(links)
