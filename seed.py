"""
Seed the database with realistic demo articles so all features are demonstrable
even without live network access.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from engine import init_db, get_db, build_embeddings, article_id
import datetime

DEMO_ARTICLES = [
    # AI / Technology
    ("AI", "OpenAI Releases GPT-5 With Reasoning Breakthrough", "https://techcrunch.com/gpt5-reasoning",
     "techcrunch.com", "OpenAI has unveiled GPT-5, its most capable language model to date. The model demonstrates significant improvements in multi-step reasoning, coding, and scientific problem-solving. Early benchmarks show GPT-5 outperforming human experts in several domains including mathematics and medicine. The company says the model was trained with new safety techniques developed over the past year."),
    ("AI", "Google DeepMind AlphaFold 3 Predicts Protein-Drug Interactions", "https://nature.com/alphafold3",
     "nature.com", "Google DeepMind has released AlphaFold 3, extending the system's capabilities from predicting protein structures to modelling how drugs interact with biological molecules. Researchers say this could cut years off the drug discovery process. AlphaFold 3 can now predict the structures of DNA, RNA, and small molecules alongside proteins."),
    ("AI", "Meta Open-Sources Llama 4 as AI Race Intensifies", "https://meta.ai/llama4",
     "meta.com", "Meta has released Llama 4, its latest open-source large language model. The release comes amid fierce competition between AI labs. Llama 4 features improved instruction following and multilingual capabilities. Meta says open-sourcing the model will benefit researchers globally and help democratise AI development."),
    ("AI", "Claude 4 by Anthropic Sets New Safety Benchmarks", "https://anthropic.com/claude4",
     "anthropic.com", "Anthropic has released Claude 4, claiming it is the most steerable and safety-focused frontier model yet. The model excels at long-context tasks and demonstrates improved honesty. Anthropic published a detailed safety card alongside the release outlining how the model handles sensitive topics."),
    ("AI", "Nvidia H200 GPU Demand Surges as AI Training Costs Fall", "https://wsj.com/nvidia-h200",
     "wsj.com", "Demand for Nvidia's H200 GPUs has surged as major AI labs race to train the next generation of models. Despite growing supply, prices remain elevated. Meanwhile, new efficient training techniques are helping reduce the cost of training large models, potentially democratising AI development."),

    # Technology
    ("Technology", "Apple Vision Pro 2 Announced With Eye-Tracking Keyboard", "https://apple.com/vision-pro-2",
     "apple.com", "Apple has announced Vision Pro 2 featuring a redesigned eye-tracking keyboard and a lighter form factor. The new headset weighs 30 percent less than its predecessor and offers improved battery life. Apple also revealed spatial computing APIs that let developers build immersive productivity apps."),
    ("Technology", "Microsoft Integrates Copilot Deeper Into Windows 12", "https://microsoft.com/windows12",
     "microsoft.com", "Microsoft has announced that its Copilot AI assistant will be deeply integrated into Windows 12, handling tasks like file organisation, email drafting, and system settings. The company says AI features will run locally on devices with Snapdragon X chips, protecting user privacy."),
    ("Technology", "SpaceX Starship Successfully Completes First Orbital Flight", "https://spacex.com/starship-orbital",
     "spacex.com", "SpaceX's Starship rocket completed its first successful orbital flight, marking a major milestone for the company's Mars ambitions. The 120-metre-tall vehicle launched from Boca Chica, Texas, completed one orbit, and landed its Super Heavy booster back on the launch pad. Elon Musk called it a pivotal moment for humanity."),

    # Business
    ("Business", "Federal Reserve Holds Interest Rates Steady Amid Inflation Concerns", "https://reuters.com/fed-rates",
     "reuters.com", "The US Federal Reserve held interest rates steady at its latest meeting, citing persistent inflation concerns. Fed Chair Jerome Powell signalled that rate cuts are unlikely before inflation returns closer to the 2 percent target. Markets had been expecting a cut later this year."),
    ("Business", "Amazon Reports Record Q1 Profits Driven by AWS AI Services", "https://bloomberg.com/amazon-q1",
     "bloomberg.com", "Amazon reported record first-quarter profits, driven primarily by surging demand for artificial intelligence services through its AWS cloud division. AWS revenue grew 32 percent year-over-year. Amazon CEO Andy Jassy credited heavy investment in AI infrastructure for the results."),
    ("Business", "Tesla Cuts EV Prices Again as Competition Heats Up", "https://ft.com/tesla-prices",
     "ft.com", "Tesla has cut prices on its Model 3 and Model Y vehicles for the third time this year, as competition from Chinese electric vehicle makers intensifies. BYD now outsells Tesla in several European markets. Analysts say Tesla may need to sacrifice margins to maintain market share."),
    ("Business", "India GDP Grows 7.8% Making It World's Fastest Growing Economy", "https://economictimes.com/india-gdp",
     "economictimes.com", "India's GDP grew at 7.8 percent in the latest quarter, cementing its position as the world's fastest-growing major economy. Growth was driven by manufacturing, services, and government infrastructure spending. The IMF has revised India's growth forecast upward to 7.5 percent for the full year."),

    # World
    ("World", "G7 Nations Agree on New AI Governance Framework", "https://bbc.com/g7-ai",
     "bbc.com", "Leaders of the G7 nations have agreed on a landmark framework for governing artificial intelligence, requiring transparency from AI developers and establishing cross-border cooperation on AI safety. The agreement includes provisions for auditing powerful AI systems and sharing safety research."),
    ("World", "UN Climate Summit Sets New Carbon Targets for 2035", "https://guardian.com/climate-summit",
     "guardian.com", "A United Nations climate summit ended with 120 nations committing to new carbon reduction targets for 2035. The agreement calls for a 45 percent reduction in emissions from 2010 levels. Critics say the targets fall short of what scientists say is needed to limit warming to 1.5 degrees Celsius."),
    ("World", "Ukraine Receives First European Fighter Jets", "https://reuters.com/ukraine-jets",
     "reuters.com", "Ukraine has received its first batch of F-16 fighter jets from European allies. Ukrainian pilots trained in the Netherlands and Denmark are now flying the aircraft on combat missions. Ukrainian officials say the jets will significantly improve the country's air defence capabilities."),

    # Science
    ("Science", "Scientists Discover New Antibiotic That Kills Drug-Resistant Bacteria", "https://nature.com/antibiotic",
     "nature.com", "Researchers have discovered a new antibiotic capable of killing several strains of drug-resistant bacteria. The compound, derived from a soil bacterium, targets a mechanism that has not been exploited by existing antibiotics. Scientists say it could be a major breakthrough in the fight against antimicrobial resistance."),
    ("Science", "James Webb Telescope Finds Evidence of Liquid Water on Distant Moon", "https://nasa.gov/webb-water",
     "nasa.gov", "NASA's James Webb Space Telescope has detected strong evidence of liquid water on a moon orbiting a distant gas giant. The discovery raises the possibility of habitable environments beyond our solar system. Scientists caution that further observations are needed to confirm the finding."),
    ("Science", "CERN Announces Plans for Larger Particle Collider", "https://cern.ch/fcc",
     "cern.ch", "CERN has announced plans for the Future Circular Collider, a particle accelerator four times larger than the current Large Hadron Collider. The project, estimated to cost 20 billion euros, would enable physicists to probe the fundamental structure of matter at unprecedented energy levels."),

    # India
    ("India", "India Launches World's Largest Solar Farm in Rajasthan", "https://ndtv.com/india-solar",
     "ndtv.com", "India has inaugurated the world's largest solar farm in the Thar Desert of Rajasthan. The 30-gigawatt facility is part of India's ambitious plan to reach 500 gigawatts of renewable energy by 2030. Prime Minister Modi called it a testament to India's commitment to clean energy."),
    ("India", "ISRO's Chandrayaan-4 Mission Targets Moon Sample Return", "https://isro.gov.in/chandrayaan4",
     "isro.gov.in", "India's space agency ISRO has outlined plans for the Chandrayaan-4 mission, which aims to collect and return samples from the lunar surface. The mission builds on the success of Chandrayaan-3, which landed near the Moon's south pole. Launch is expected in 2026."),
]

def seed():
    print("Initialising database...")
    init_db()
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    conn.close()
    
    if count > 0:
        print(f"DB already has {count} articles. Skipping seed.")
        return count

    print(f"Seeding {len(DEMO_ARTICLES)} demo articles...")
    conn = get_db()
    now = datetime.datetime.utcnow().isoformat()
    article_texts = []
    
    for category, title, url, source, summary in DEMO_ARTICLES:
        aid = article_id(url)
        conn.execute("INSERT OR IGNORE INTO articles VALUES (?,?,?,?,?,?,?,?)",
                     (aid, title, url, source, category,
                      datetime.datetime.utcnow().strftime("%a, %d %b %Y 12:00:00 +0000"),
                      summary, now))
        text = title + ". " + summary
        article_texts.append((aid, text))
    
    conn.commit()
    conn.close()
    
    print("Building embeddings (TF-IDF vectors)...")
    build_embeddings(article_texts)
    
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()
    print(f"Done! {total} articles, {chunks} chunks indexed.")
    return total

if __name__ == "__main__":
    seed()
