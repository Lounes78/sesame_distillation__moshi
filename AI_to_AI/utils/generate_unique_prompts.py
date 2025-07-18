import os
import pandas as pd
import time
import random
from anthropic import AnthropicVertex
from difflib import SequenceMatcher

# Set up authentication and project
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/home/lounes/.config/gcloud/application_default_credentials.json'
PROJECT_ID = ''
LOCATION = 'us-east5'

class UniquePromptGenerator:
    def __init__(self, input_csv_path, output_csv_path):
        self.input_csv_path = input_csv_path
        self.output_csv_path = output_csv_path
        self.client = AnthropicVertex(project_id=PROJECT_ID, region=LOCATION)
        self.existing_prompts = set()
        self.voice_toggle = True  # Start with 'zac'
        self.current_prompt_id = 1081  # Start from 1081
        self.load_existing_prompts()
        
    def load_existing_prompts(self):
        """Load existing prompts to avoid duplicates"""
        try:
            df = pd.read_csv(self.input_csv_path)
            # Get the prompt column
            prompt_col = None
            for col in ['text', 'prompt', 'content']:
                if col in df.columns:
                    prompt_col = col
                    break
            if prompt_col is None:
                prompt_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]  # Assume second column if first is ID
            
            # Clean and store existing prompts
            for prompt in df[prompt_col].dropna():
                cleaned = self.clean_prompt(str(prompt))
                if cleaned:
                    self.existing_prompts.add(cleaned)
            
            print(f"Loaded {len(self.existing_prompts)} existing prompts from {self.input_csv_path}")
            
            # Create output file with same structure if it doesn't exist
            if not os.path.exists(self.output_csv_path):
                df_empty = df.iloc[:0].copy()  # Empty dataframe with same columns
                df_empty.to_csv(self.output_csv_path, index=False)
                print(f"Created new output file: {self.output_csv_path}")
            else:
                # Load existing output prompts too and update prompt_id counter
                df_output = pd.read_csv(self.output_csv_path)
                if len(df_output) > 0:
                    # Update current_prompt_id to continue from the last ID
                    if 'prompt_id' in df_output.columns:
                        self.current_prompt_id = df_output['prompt_id'].max() + 1
                    
                    for prompt in df_output[prompt_col].dropna():
                        cleaned = self.clean_prompt(str(prompt))
                        if cleaned:
                            self.existing_prompts.add(cleaned)
                    print(f"Also loaded {len(df_output)} prompts from existing output file")
                    print(f"Next prompt_id will be: {self.current_prompt_id}")
                
        except Exception as e:
            print(f"Error loading existing prompts: {e}")
            
    def clean_prompt(self, prompt):
        """Clean prompt for comparison"""
        return prompt.lower().strip().replace('"', '').replace("'", "")
    
    def is_similar(self, new_prompt, threshold=0.85):
        """Check if new prompt is too similar to existing ones with AI fallback"""
        cleaned_new = self.clean_prompt(new_prompt)
        
        # First pass: exact match
        if cleaned_new in self.existing_prompts:
            return True
        
        # Second pass: text similarity with lower threshold for AI check
        uncertain_cases = []
        
        for existing in self.existing_prompts:
            similarity = SequenceMatcher(None, cleaned_new, existing).ratio()
            
            # Definite duplicate
            if similarity > threshold:
                return True
            
            # Uncertain zone - collect for AI analysis
            elif similarity > 0.65:  # Lower threshold for AI check
                uncertain_cases.append((existing, similarity))
        
        # If we have uncertain cases, ask AI to judge
        if uncertain_cases:
            # Sort by similarity and take top 3 most similar
            uncertain_cases.sort(key=lambda x: x[1], reverse=True)
            top_uncertain = uncertain_cases[:3]
            
            return self.ai_similarity_check(new_prompt, top_uncertain)
        
        return False
    
    def ai_similarity_check(self, new_prompt, similar_prompts):
        """Use AI to determine if prompts are too similar"""
        try:
            # Create comparison prompt for AI
            existing_list = "\n".join([f"- {prompt}" for prompt, score in similar_prompts])
            
            ai_prompt = f"""
You are an expert at detecting duplicate or overly similar conversation starters.

NEW PROMPT: "{new_prompt}"

EXISTING SIMILAR PROMPTS:
{existing_list}

TASK: Determine if the NEW PROMPT is too similar to any of the existing prompts.

Consider these as TOO SIMILAR:
- Same core question with different wording
- Same topic with nearly identical intent
- Asking the same thing in different ways
- Would generate very similar responses

Consider these as DIFFERENT ENOUGH:
- Different aspects of the same broad topic
- Different question types (how vs what vs when)
- Different scope or specificity
- Would generate notably different responses

Respond with ONLY:
"DUPLICATE" - if too similar to existing prompts
"UNIQUE" - if sufficiently different

Your answer:"""

            message = self.client.messages.create(
                model="claude-sonnet-4@20250514",
                max_tokens=50,
                temperature=0.1,  # Low temperature for consistent judgment
                messages=[{"role": "user", "content": ai_prompt}]
            )
            
            response = message.content[0].text.strip().upper()
            
            if "DUPLICATE" in response:
                print(f"🤖 AI detected similarity: {new_prompt[:50]}...")
                return True
            elif "UNIQUE" in response:
                print(f"🤖 AI approved uniqueness: {new_prompt[:50]}...")
                return False
            else:
                # AI gave unclear response, err on side of caution
                print(f"🤖 AI unclear response '{response}', marking as duplicate")
                return True
                
        except Exception as e:
            print(f"❌ AI similarity check failed: {e}")
            # Fallback to conservative approach - mark as duplicate if AI fails
            return True
    
    def generate_batch_prompts(self, batch_size=10):
        """Generate a batch of unique prompts"""
        
        # Varied prompt strategies to ensure diversity
        strategies = [
            "Generate conversation starters about daily life experiences and personal habits",
            "Create prompts about technology, innovation, and digital life",
            "Generate questions about relationships, family, and social connections",
            "Create conversation starters about creativity, arts, and self-expression",
            "Generate prompts about health, wellness, and personal growth",
            "Create questions about work, career, and professional life",
            "Generate conversation starters about travel, culture, and exploration",
            "Create prompts about learning, education, and skill development",
            "Generate questions about entertainment, hobbies, and leisure activities",
            "Create conversation starters about future aspirations and life goals",
            "Generate prompts about decision-making and life choices",
            "Create questions about memories, nostalgia, and past experiences",
            "Generate conversation starters about personal values and beliefs",
            "Create prompts about problem-solving and challenges",
            "Generate questions about seasonal preferences and environmental awareness"
        ]
        
        strategy = random.choice(strategies)
        
        # Extended variety of question structures
        question_structures = [
            "What's your perspective on...", "How do you approach...", "When did you first...", 
            "Why do people tend to...", "If you could change...", "Tell me about a time when...",
            "What draws you to...", "How has technology affected...", "In what ways do you...",
            "What would happen if...", "Describe your ideal...", "How do you balance...",
            "What's the most surprising thing about...", "If you had to choose between...",
            "What role does... play in...", "How important is... to you?", "What's your take on...",
            "When you think about...", "What's your experience with...", "How do you handle...",
            "What motivates you to...", "If money wasn't a factor...", "What's one thing about... that...",
            "How would you explain... to someone who...", "What's your biggest challenge with...",
            "If you could master any...", "What's the difference between...", "How do you decide...",
            "What's your favorite way to...", "When do you feel most...", "What would you do if...",
            "How has your relationship with... changed?", "What's something about... that surprises people?",
            "If you could go back and...", "What's your process for...", "How do you stay motivated when...",
            "What's one skill you wish...", "If you could have a conversation with...",
            "What's your philosophy on...", "How do you define...", "What's the best advice about... you've received?",
            "If you could eliminate one thing about...", "What's your unpopular opinion about...",
            "How do you think... will evolve?", "What's something you've learned recently about...",
            "If you could redesign...", "What's your relationship with...", "How do you cope with...",
            "What's one assumption people make about... that's wrong?", "If you could travel back to...",
            "What's your secret to...", "How do you know when...", "What's the hardest part about...",
            "If you could ask one question about...", "What's changed about your views on...",
            "How do you choose what... to...", "What's something everyone should know about...",
            "If you could live in a world where...", "What's your biggest misconception about...",
            "How do you think... affects...", "What's one thing you'd tell your younger self about...",
            "If you could have unlimited access to...", "What's your most memorable experience with...",
            "How do you think people in 100 years will view...", "What's something you do differently than most people when it comes to...",
            "If you could change one rule about...", "What's the most valuable lesson... has taught you?",
            "How do you think... would be different if...", "What's one trend in... that excites you?",
            "If you could be recognized as an expert in...", "What's something about... that you wish more people understood?",
            "How do you think your... compares to others your age?", "What's one thing about... that always makes you smile?",
            "If you could witness the invention of...", "What's your prediction for the future of...?",
            "How do you think... shapes who we are?", "What's one piece of conventional wisdom about... that you disagree with?"
        ]
        
        selected_structures = random.sample(question_structures, min(8, len(question_structures)))
        structure_list = "', '".join(selected_structures)
        
        prompt = f"""
{strategy}. Requirements:

- Generate {batch_size} completely unique conversation starters
- Maximum 30 words each
- Use varied question structures like: '{structure_list}', and similar patterns
- Focus on different aspects and angles of the topic
- Make them engaging, thought-provoking, and natural
- Avoid generic, cliché, or obvious questions
- Each should feel fresh, specific, and spark genuine conversation
- Mix direct questions with scenario-based prompts
- Include both introspective and observational angles

Return ONLY the prompts, one per line, numbered 1-{batch_size}.
"""
        
        try:
            message = self.client.messages.create(
                model="claude-sonnet-4@20250514",
                max_tokens=1000,
                temperature=0.9,  # Higher temperature for more variety
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text
            
            # Extract prompts from response
            prompts = []
            for line in response_text.split('\n'):
                line = line.strip()
                if line and any(line.startswith(f"{i}.") for i in range(1, batch_size + 1)):
                    # Remove number and clean up
                    prompt_text = line.split('.', 1)[1].strip()
                    if prompt_text:
                        prompts.append(prompt_text)
            
            return prompts
            
        except Exception as e:
            print(f"Error generating batch: {e}")
            return []
    
    def add_prompt_to_csv(self, prompt):
        """Add a new prompt to the output CSV"""
        try:
            # Read current CSV structure
            df_template = pd.read_csv(self.input_csv_path, nrows=1)
            
            # Create new row
            new_row = df_template.iloc[0].copy()
            
            # Set the prompt_id
            if 'prompt_id' in new_row:
                new_row['prompt_id'] = self.current_prompt_id
                self.current_prompt_id += 1
            
            # Set the prompt text
            prompt_col = None
            for col in ['text', 'prompt', 'content']:
                if col in df_template.columns:
                    prompt_col = col
                    break
            if prompt_col is None:
                prompt_col = df_template.columns[1] if len(df_template.columns) > 1 else df_template.columns[0]
            
            new_row[prompt_col] = prompt
            
            # Set other required fields
            if 'wav_exists' in new_row:
                new_row['wav_exists'] = False
            if 'voice' in new_row:
                new_row['voice'] = 'zac' if self.voice_toggle else 'tara'
                self.voice_toggle = not self.voice_toggle
            if 'usage_count' in new_row:
                new_row['usage_count'] = 0
            if 'audio_path' in new_row:
                # Generate audio path based on pattern
                voice = 'zac' if not self.voice_toggle else 'tara'  # Opposite because we already toggled
                new_row['audio_path'] = f"./prompts/science_{self.current_prompt_id-1}_{voice}.wav"
            if 'topic' in new_row:
                new_row['topic'] = 'science'  # Default topic, you can make this dynamic
            
            # Append to CSV
            new_row_df = pd.DataFrame([new_row])
            new_row_df.to_csv(self.output_csv_path, mode='a', header=False, index=False)
            
            return True
            
        except Exception as e:
            print(f"Error adding prompt to CSV: {e}")
            return False
    
    def generate_unique_prompts(self, target_count=2000):
        """Main function to generate unique prompts"""
        added_count = 0
        total_attempts = 0
        batch_size = 15
        
        print(f"Starting generation of {target_count} unique prompts...")
        print(f"Current unique prompts in memory: {len(self.existing_prompts)}")
        
        while added_count < target_count:
            print(f"\nProgress: {added_count}/{target_count} prompts generated")
            
            # Generate batch
            new_prompts = self.generate_batch_prompts(batch_size)
            total_attempts += len(new_prompts)
            
            batch_added = 0
            for prompt in new_prompts:
                # Check word count
                if len(prompt.split()) > 30:
                    continue
                
                # Check for duplicates (including AI-assisted check)
                if not self.is_similar(prompt):
                    # Add to existing prompts set
                    cleaned = self.clean_prompt(prompt)
                    self.existing_prompts.add(cleaned)
                    
                    # Add to CSV
                    if self.add_prompt_to_csv(prompt):
                        added_count += 1
                        batch_added += 1
                        print(f"✅ Added: {prompt}")
                        
                        if added_count >= target_count:
                            break
                else:
                    print(f"❌ Duplicate/Similar (detected by hardcode or AI): {prompt}")
            
            print(f"Batch results: {batch_added}/{len(new_prompts)} unique prompts added")
            
            # Small delay to avoid rate limits (increased due to AI calls)
            time.sleep(2)
            
            # If we're getting too many duplicates, increase temperature or change strategy
            if batch_added == 0 and total_attempts > added_count * 3:
                print("Warning: High duplicate rate. Adjusting generation strategy...")
                time.sleep(2)
        
        print(f"\n🎉 Successfully generated {added_count} unique prompts!")
        print(f"Total attempts: {total_attempts}")
        print(f"Success rate: {added_count/total_attempts*100:.1f}%")
        print(f"Output saved to: {self.output_csv_path}")

def main():
    input_path = "/mnt/nas/KITT/DISTILLATION/sesame_distillation__moshi/AI_to_AI/prompts/prompts.csv"
    output_path = "/mnt/nas/KITT/DISTILLATION/sesame_distillation__moshi/AI_to_AI/prompts/prompts2.csv"
    
    generator = UniquePromptGenerator(input_path, output_path)
    generator.generate_unique_prompts(target_count=2000)

if __name__ == "__main__":
    main()