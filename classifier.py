import re
from collections import defaultdict
from database.database import MetadataDatabase
from logger import logger

class AdvancedISICClassifier:
    def __init__(self, db):
        self.db = db
        
        # Expanded ISIC Rev. 5 Taxonomy to match the broad scope of your config.py
        self.taxonomy = {
            "Division 72: Scientific research and development": [
                r"\bresearch\b", r"\bscience\b", r"\blaboratory\b", r"\bstudy\b", r"\bexperiment\b",
                r"\bethnography\b", r"\bmethodology\b", r"\bphenomenology\b", r"\bqualitative\b"
            ],
            "Division 85: Education": [
                r"\beducation\b", r"\bschool\b", r"\buniversity\b", r"\bstudent\b", r"\bteacher\b", 
                r"\blearning\b", r"\bpedagogy\b", r"\bacademic\b", r"\bcurriculum\b"
            ],
            "Division 86: Human health activities": [
                r"\bhealth\b", r"\bmedical\b", r"\bpatient\b", r"\bdisease\b", r"\bclinical\b", 
                r"\bhospital\b", r"\bnursing\b", r"\bpsychology\b", r"\btherapy\b"
            ],
            "Division 84: Public administration and defence": [
                r"\bgovernment\b", r"\bpolicy\b", r"\bpublic sector\b", r"\bmunicipality\b", 
                r"\bcivic\b", r"\binstitution\b"
            ],
            "Division 94: Activities of membership organizations": [
                r"\bunion\b", r"\bngo\b", r"\bnon-profit\b", r"\bassociation\b", r"\bcommunity\b", 
                r"\bsociety\b"
            ],
            "Division 62: Computer programming and consultancy": [
                r"\bsoftware\b", r"\bit\b", r"\btechnology\b", r"\bprogramming\b", r"\bdata\b", 
                r"\balgorithm\b", r"\bdigital\b"
            ]
        }

        # Words to ignore so we don't fill the KEYWORDS table with junk
        self.stop_words = {
            "without", "through", "between", "because", "therefore", "however", 
            "although", "another", "against", "further", "whether", "during",
            "should", "would", "could", "project", "dataset", "version"
        }

    def clean_text(self, text):
        if not text: 
            return ""
        # Remove URLs and special characters, convert to lowercase
        text = re.sub(r'http\S+', '', text)
        text = re.sub(r'[^a-zA-Z\s]', ' ', text)
        return text.lower()

    def extract_tags(self, cleaned_text):
        if not cleaned_text: 
            return []
        words = cleaned_text.split()
        
        # Extract meaningful words (6+ letters) that are NOT in the stop_words list
        tags = [w for w in words if len(w) >= 6 and w not in self.stop_words]
        
        # Return the top 6 unique tags to keep the database optimized
        unique_tags = list(dict.fromkeys(tags))[:6]
        return unique_tags

    def classify(self, text):
        cleaned_text = self.clean_text(text)
        if not cleaned_text: 
            return "Unclassified"
            
        scores = defaultdict(int)
        for division, patterns in self.taxonomy.items():
            for pattern in patterns:
                matches = len(re.findall(pattern, cleaned_text))
                if matches > 0:
                    scores[division] += matches
                    
        # Return the division with the highest score
        if scores:
            return max(scores, key=scores.get)
        return "Unclassified"

    def run(self):
        logger.info("Initializing ISIC Rev. 5 Classification into KEYWORDS table...")
        
        # Fetch projects from the normalized database
        unclassified_projects = self.db.get_unclassified_projects()
        
        if not unclassified_projects:
            logger.info("All projects are fully classified. No new records found.")
            return

        success_count = 0
        
        for proj_id, title, description in unclassified_projects:
            # Safely handle None types to prevent concatenation crashes
            safe_title = title or ""
            safe_desc = description or ""
            context_text = f"{safe_title} {safe_desc}"
            
            isic_division = self.classify(context_text)
            tags = self.extract_tags(self.clean_text(context_text))
            
            if isic_division != "Unclassified":
                # Insert ISIC classification as a structured keyword
                self.db.add_keyword(proj_id, f"ISIC:{isic_division}")
                success_count += 1
                
            # Insert the cleaned, auto-generated descriptive tags
            for tag in tags:
                self.db.add_keyword(proj_id, tag)
                
        logger.info(f"Classification Complete. Successfully mapped {success_count} new projects.")

if __name__ == "__main__":
    db = MetadataDatabase()
    classifier = AdvancedISICClassifier(db)
    classifier.run()
    db.close()
