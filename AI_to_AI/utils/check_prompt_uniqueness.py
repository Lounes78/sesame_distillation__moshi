import pandas as pd
import os
import multiprocessing as mp
from collections import Counter
from difflib import SequenceMatcher
from functools import partial
import math
import time

def clean_prompt(prompt):
    """Clean prompt for comparison (same as in generate_unique_prompts.py)"""
    return str(prompt).lower().strip().replace('"', '').replace("'", "")

def compare_prompt_chunk(chunk_data):
    """
    Compare a chunk of prompt pairs for similarity.
    
    Args:
        chunk_data: Tuple containing (prompt_pairs_chunk, similarity_threshold)
    
    Returns:
        List of similar pairs found in this chunk
    """
    prompt_pairs_chunk, similarity_threshold = chunk_data
    similar_pairs = []
    
    for prompt1, prompt2 in prompt_pairs_chunk:
        similarity = SequenceMatcher(None, prompt1['cleaned'], prompt2['cleaned']).ratio()
        
        if similarity >= similarity_threshold:
            similar_pairs.append({
                'prompt1': prompt1,
                'prompt2': prompt2,
                'similarity': similarity
            })
    
    return similar_pairs

def get_optimal_worker_count():
    """
    Determine the optimal number of worker processes based on system capabilities.
    
    Returns:
        int: Number of worker processes to use
    """
    cpu_count = mp.cpu_count()
    # Use 75% of available cores, but at least 1 and at most 16
    optimal_workers = max(1, min(16, int(cpu_count * 0.75)))
    return optimal_workers

def create_prompt_pairs_chunks(all_prompts, num_workers):
    """
    Create chunks of prompt pairs for parallel processing.
    
    Args:
        all_prompts: List of all prompt objects
        num_workers: Number of worker processes
    
    Returns:
        List of chunks, where each chunk contains prompt pairs to compare
    """
    total_pairs = len(all_prompts) * (len(all_prompts) - 1) // 2
    pairs_per_chunk = max(1, total_pairs // num_workers)
    
    chunks = []
    current_chunk = []
    
    for i in range(len(all_prompts)):
        for j in range(i + 1, len(all_prompts)):
            current_chunk.append((all_prompts[i], all_prompts[j]))
            
            if len(current_chunk) >= pairs_per_chunk:
                chunks.append(current_chunk)
                current_chunk = []
    
    # Add remaining pairs to the last chunk
    if current_chunk:
        if chunks:
            chunks[-1].extend(current_chunk)
        else:
            chunks.append(current_chunk)
    
    return chunks

def check_prompt_uniqueness(csv_files, similarity_threshold=0.85, use_multiprocessing=True):
    """
    Check for duplicate and similar prompts across multiple CSV files.
    
    Args:
        csv_files: List of CSV file paths
        similarity_threshold: Threshold for considering prompts similar (0.0-1.0)
        use_multiprocessing: Whether to use multiprocessing for similarity checking
    
    Returns:
        Dictionary with analysis results
    """
    all_prompts = []
    file_prompt_counts = {}
    
    print("Loading prompts from CSV files...")
    
    for csv_file in csv_files:
        if not os.path.exists(csv_file):
            print(f"Warning: File {csv_file} does not exist, skipping...")
            continue
            
        try:
            df = pd.read_csv(csv_file)
            
            # Find the prompt column
            prompt_col = None
            for col in ['text', 'prompt', 'content']:
                if col in df.columns:
                    prompt_col = col
                    break
            if prompt_col is None:
                prompt_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
            
            # Extract prompts
            file_prompts = []
            for idx, prompt in enumerate(df[prompt_col].dropna()):
                cleaned = clean_prompt(prompt)
                if cleaned:
                    all_prompts.append({
                        'original': str(prompt),
                        'cleaned': cleaned,
                        'file': csv_file,
                        'row': idx + 2  # +2 because pandas is 0-indexed and CSV has header
                    })
                    file_prompts.append(cleaned)
            
            file_prompt_counts[csv_file] = len(file_prompts)
            print(f"  {csv_file}: {len(file_prompts)} prompts")
            
        except Exception as e:
            print(f"Error reading {csv_file}: {e}")
            continue
    
    total_prompts = len(all_prompts)
    print(f"\nTotal prompts loaded: {total_prompts}")
    
    # Check for exact duplicates
    print("\n" + "="*60)
    print("CHECKING FOR EXACT DUPLICATES")
    print("="*60)
    
    cleaned_prompts = [p['cleaned'] for p in all_prompts]
    prompt_counts = Counter(cleaned_prompts)
    exact_duplicates = {prompt: count for prompt, count in prompt_counts.items() if count > 1}
    
    if exact_duplicates:
        print(f"Found {len(exact_duplicates)} exact duplicates:")
        for prompt, count in exact_duplicates.items():
            print(f"\n  Duplicate prompt (appears {count} times):")
            print(f"    '{prompt[:100]}{'...' if len(prompt) > 100 else ''}'")
            
            # Show where each duplicate appears
            for p in all_prompts:
                if p['cleaned'] == prompt:
                    print(f"      - {p['file']} (row {p['row']})")
    else:
        print("✅ No exact duplicates found!")
    
    # Check for similar prompts
    print("\n" + "="*60)
    print(f"CHECKING FOR SIMILAR PROMPTS (threshold: {similarity_threshold})")
    print("="*60)
    
    similar_pairs = []
    
    if len(all_prompts) <= 1:
        print("✅ Not enough prompts to check for similarity!")
    else:
        total_comparisons = len(all_prompts) * (len(all_prompts) - 1) // 2
        print(f"Total comparisons to perform: {total_comparisons:,}")
        
        if use_multiprocessing and total_comparisons > 1000:  # Only use multiprocessing for larger datasets
            num_workers = get_optimal_worker_count()
            print(f"Using {num_workers} worker processes for parallel similarity checking...")
            
            start_time = time.time()
            
            # Create chunks of prompt pairs for parallel processing
            chunks = create_prompt_pairs_chunks(all_prompts, num_workers)
            print(f"Created {len(chunks)} chunks for processing")
            
            # Prepare data for multiprocessing
            chunk_data = [(chunk, similarity_threshold) for chunk in chunks]
            
            # Use multiprocessing to compare chunks in parallel
            with mp.Pool(processes=num_workers) as pool:
                chunk_results = pool.map(compare_prompt_chunk, chunk_data)
            
            # Combine results from all chunks
            for chunk_result in chunk_results:
                similar_pairs.extend(chunk_result)
            
            end_time = time.time()
            print(f"Parallel similarity checking completed in {end_time - start_time:.2f} seconds")
            
        else:
            # Use single-threaded approach for smaller datasets or when multiprocessing is disabled
            print("Using single-threaded similarity checking...")
            start_time = time.time()
            
            for i in range(len(all_prompts)):
                if i % 100 == 0 and i > 0:
                    print(f"  Processed {i}/{len(all_prompts)} prompts...")
                
                for j in range(i + 1, len(all_prompts)):
                    prompt1 = all_prompts[i]
                    prompt2 = all_prompts[j]
                    
                    similarity = SequenceMatcher(None, prompt1['cleaned'], prompt2['cleaned']).ratio()
                    
                    if similarity >= similarity_threshold:
                        similar_pairs.append({
                            'prompt1': prompt1,
                            'prompt2': prompt2,
                            'similarity': similarity
                        })
            
            end_time = time.time()
            print(f"Single-threaded similarity checking completed in {end_time - start_time:.2f} seconds")
    
    if similar_pairs:
        print(f"Found {len(similar_pairs)} similar prompt pairs:")
        for pair in similar_pairs:
            print(f"\n  Similarity: {pair['similarity']:.3f}")
            print(f"    1: '{pair['prompt1']['original'][:80]}{'...' if len(pair['prompt1']['original']) > 80 else ''}'")
            print(f"       ({pair['prompt1']['file']} row {pair['prompt1']['row']})")
            print(f"    2: '{pair['prompt2']['original'][:80]}{'...' if len(pair['prompt2']['original']) > 80 else ''}'")
            print(f"       ({pair['prompt2']['file']} row {pair['prompt2']['row']})")
    else:
        print(f"✅ No similar prompts found above {similarity_threshold} threshold!")
    
    # Summary statistics
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    unique_prompts = len(set(cleaned_prompts))
    
    print(f"Total prompts: {total_prompts}")
    print(f"Unique prompts: {unique_prompts}")
    print(f"Duplicate prompts: {total_prompts - unique_prompts}")
    print(f"Uniqueness rate: {unique_prompts/total_prompts*100:.1f}%")
    
    print(f"\nFile breakdown:")
    for file, count in file_prompt_counts.items():
        print(f"  {os.path.basename(file)}: {count} prompts")
    
    # Performance info
    if use_multiprocessing and len(all_prompts) > 1:
        total_comparisons = len(all_prompts) * (len(all_prompts) - 1) // 2
        print(f"\nPerformance info:")
        print(f"  Total comparisons: {total_comparisons:,}")
        print(f"  Used multiprocessing: {'Yes' if total_comparisons > 1000 else 'No (dataset too small)'}")
        if total_comparisons > 1000:
            print(f"  Worker processes: {get_optimal_worker_count()}")
    
    return {
        'total_prompts': total_prompts,
        'unique_prompts': unique_prompts,
        'exact_duplicates': exact_duplicates,
        'similar_pairs': similar_pairs,
        'file_counts': file_prompt_counts
    }

def main():
    """Main function to check prompt uniqueness in the default CSV files"""
    csv_files = [
        "prompts/prompts.csv",
        "prompts/prompts2.csv"
    ]
    
    # Convert to absolute paths
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_files = [os.path.join(script_dir, f) for f in csv_files]
    
    print("Checking prompt uniqueness across CSV files...")
    print("Files to check:")
    for f in csv_files:
        print(f"  - {f}")
    
    # Show system info
    print(f"\nSystem info:")
    print(f"  CPU cores available: {mp.cpu_count()}")
    print(f"  Optimal worker processes: {get_optimal_worker_count()}")
    
    results = check_prompt_uniqueness(csv_files, similarity_threshold=0.85, use_multiprocessing=True)
    
    print(f"\n🎯 Analysis complete!")
    if results['exact_duplicates']:
        print(f"⚠️  Found {len(results['exact_duplicates'])} exact duplicates")
    if results['similar_pairs']:
        print(f"⚠️  Found {len(results['similar_pairs'])} similar pairs")
    if not results['exact_duplicates'] and not results['similar_pairs']:
        print("✅ All prompts are unique!")

if __name__ == "__main__":
    main()