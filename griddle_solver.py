import json
import os
import sys
import urllib.request
import time
from collections import Counter
import concurrent.futures

# ==========================================
# 3. & 4. RECURSIVE ENGINE & SCORING (WORKER)
# (Moved to top-level for Windows multiprocessing)
# ==========================================
def solve_chunk(args):
    opt0, opt1, pool_str, grid_size, valid_words, valid_prefixes, letter_values, multipliers = args
    
    current_grid = [["" for _ in range(grid_size)] for _ in range(grid_size)]
    current_grid[0][0] = opt0
    current_grid[0][1] = opt1
    
    pool_counts = Counter(pool_str)
    if opt0: pool_counts[opt0] -= 1
    if opt1: pool_counts[opt1] -= 1
    
    best_score = 0
    best_board = None

    def is_valid_placement(row, col, placing_blank):
        h_str = ""
        c = col if not placing_blank else col - 1
        while c >= 0 and current_grid[row][c] != "":
            h_str = current_grid[row][c] + h_str
            c -= 1
            
        v_str = ""
        r = row if not placing_blank else row - 1
        while r >= 0 and current_grid[r][col] != "":
            v_str = current_grid[r][col] + v_str
            r -= 1

        for string in (h_str, v_str):
            if len(string) >= 2:
                if placing_blank and string not in valid_words:
                    return False
                if not placing_blank and string not in valid_prefixes:
                    return False
        return True

    def evaluate_completed_board():
        nonlocal best_score, best_board
        found_words = []
        
        # 1. Extract Horizontal Words
        for r in range(grid_size):
            curr_word, curr_coords = "", []
            for c in range(grid_size):
                char = current_grid[r][c]
                if char != "":
                    curr_word += char
                    curr_coords.append((r, c))
                else:
                    if len(curr_word) >= 2: found_words.append({"word": curr_word, "coords": curr_coords})
                    curr_word, curr_coords = "", []
            if len(curr_word) >= 2: found_words.append({"word": curr_word, "coords": curr_coords})

        # 2. Extract Vertical Words
        for c in range(grid_size):
            curr_word, curr_coords = "", []
            for r in range(grid_size):
                char = current_grid[r][c]
                if char != "":
                    curr_word += char
                    curr_coords.append((r, c))
                else:
                    if len(curr_word) >= 2: found_words.append({"word": curr_word, "coords": curr_coords})
                    curr_word, curr_coords = "", []
            if len(curr_word) >= 2: found_words.append({"word": curr_word, "coords": curr_coords})
        
        # --- STRICT VALIDATION BLOCK ---
        for item in found_words:
            if item["word"] not in valid_words:
                return

        # 3. Calculate Score
        total_score = 0
        valid_coords = set()
        
        for item in found_words:
            word = item["word"]
            coords = item["coords"]
            valid_coords.update(coords)
            
            word_score = 0
            word_mult_factor = 1
            
            for i, (r, c) in enumerate(coords):
                char_score = letter_values.get(word[i], 0)
                for mult in multipliers:
                    if mult["row"] == r and mult["col"] == c:
                        if mult["type"] == 'L':
                            char_score *= mult["value"]
                        elif mult["type"] == 'W':
                            word_mult_factor *= mult["value"]
                word_score += char_score
                
            total_score += (word_score * word_mult_factor)
            
        # 4. Update Champion Board
        if total_score > best_score:
            best_score = total_score
            best_board = [["" for _ in range(grid_size)] for _ in range(grid_size)]
            for r in range(grid_size):
                for c in range(grid_size):
                    if (r, c) in valid_coords:
                        best_board[r][c] = current_grid[r][c]

    def backtrack(cell_index):
        if cell_index == 16:
            evaluate_completed_board()
            return

        row = cell_index // grid_size
        col = cell_index % grid_size

        # Option 1: Leave Blank
        current_grid[row][col] = ""
        if is_valid_placement(row, col, placing_blank=True):
            backtrack(cell_index + 1)

        # Option 2: Place Letter
        available_letters = [char for char, count in pool_counts.items() if count > 0]
        for letter in set(available_letters):
            current_grid[row][col] = letter
            pool_counts[letter] -= 1
            if is_valid_placement(row, col, placing_blank=False):
                backtrack(cell_index + 1)
            current_grid[row][col] = ""
            pool_counts[letter] += 1

    if not is_valid_placement(0, 0, placing_blank=(opt0 == "")): return 0, None
    if not is_valid_placement(0, 1, placing_blank=(opt1 == "")): return 0, None

    backtrack(2)
    return best_score, best_board


# ==========================================
# MAIN APPLICATION CLASS
# ==========================================
class GridWordSolver:
    def __init__(self):
        self.grid_size = 4
        self.letter_pool = []
        self.letter_values = {}
        self.multipliers = []  
        self.valid_words = set()
        self.blacklist = set()
        self.best_board = None
        self.best_score = 0

    # ==========================================
    # 1. SETUP & I/O
    # ==========================================
    def load_and_prompt_letters(self):
        json_file = "letter_values.json"
        if os.path.exists(json_file):
            with open(json_file, 'r') as f:
                self.letter_values = json.load(f)

        blacklist_file = "blacklist.json"
        if os.path.exists(blacklist_file):
            with open(blacklist_file, 'r') as f:
                self.blacklist = set(json.load(f))
        
        print("Enter your 10 letters (you can type them one by one or all at once):")
        while len(self.letter_pool) < 10:
            user_input = input(f"Letters captured ({len(self.letter_pool)}/10): ").strip().upper()
            
            for char in user_input:
                if char.isalpha() and len(self.letter_pool) < 10:
                    self.letter_pool.append(char)
                    if char not in self.letter_values:
                        while True:
                            try:
                                val = int(input(f"New letter detected! Enter point value for '{char}': "))
                                self.letter_values[char] = val
                                break
                            except ValueError:
                                print("Please enter a valid integer.")
        
        with open(json_file, 'w') as f:
            json.dump(self.letter_values, f, indent=4)

    def confirm_letter_values(self):
        print("\n--- Current Letter Values ---")
        for letter in set(self.letter_pool):
            print(f"{letter}: {self.letter_values[letter]}")
        
        while True:
            confirm = input("\nAre these values correct? (Y/N): ").strip().upper()
            if confirm == 'Y':
                break
            elif confirm == 'N':
                letter_to_fix = input("Which letter do you want to fix? ").strip().upper()
                if letter_to_fix in self.letter_values:
                    try:
                        new_val = int(input(f"Enter new point value for '{letter_to_fix}': "))
                        self.letter_values[letter_to_fix] = new_val
                        with open("letter_values.json", 'w') as f:
                            json.dump(self.letter_values, f, indent=4)
                        self.confirm_letter_values() 
                        return
                    except ValueError:
                        print("Invalid number. Please try again.")
                else:
                    print("That letter isn't in your current pool.")
            else:
                print("Please enter Y or N.")

    def get_multipliers(self):
        self.multipliers.clear()
        while True:
            has_mult = input("\nAdd a multiplier? (Y/N): ").strip().upper()
            if has_mult == 'N':
                break
            elif has_mult == 'Y':
                try:
                    row = int(input("Enter row (1-4): ")) - 1
                    col = int(input("Enter column (1-4): ")) - 1
                    if not (0 <= row <= 3 and 0 <= col <= 3):
                        print("Coordinates must be between 1 and 4.")
                        continue
                        
                    m_type = input("Is this a Letter or Word multiplier? (L/W): ").strip().upper()
                    if m_type not in ['L', 'W']:
                        print("Please enter L or W.")
                        continue
                        
                    val = int(input("Enter multiplier value (e.g., 2, 3): "))
                    self.multipliers.append({"row": row, "col": col, "value": val, "type": m_type})
                    
                    m_name = "Letter" if m_type == 'L' else "Word"
                    print(f"-> {m_name} Multiplier added at [Row {row+1}, Col {col+1}] with {val}x value.")
                except ValueError:
                    print("Invalid input. Please use integers.")
            else:
                print("Please enter Y or N.")

    # ==========================================
    # 2. DICTIONARY & PRUNING
    # ==========================================
    def build_pruned_dictionary(self):
        self.valid_words.clear()
        master_word_list = set()
        
        # 1. Load NLTK
        import nltk
        try:
            nltk.data.find('corpora/words')
        except LookupError:
            print("\n[INFO] Downloading NLTK English word corpus...")
            nltk.download('words', quiet=True)
        from nltk.corpus import words
        master_word_list.update(w.upper() for w in words.words())
        
        # 2. Batch Download & Load External Dictionaries
        dict_sources = {
            "enable1.txt": "https://raw.githubusercontent.com/dolph/dictionary/master/enable1.txt",
            "sowpods.txt": "https://raw.githubusercontent.com/jesstess/Scrabble/master/scrabble/sowpods.txt",
            "twl06.txt": "https://raw.githubusercontent.com/cviebrock/wordlists/master/TWL06.txt",
            "ospd.txt": "https://raw.githubusercontent.com/dolph/dictionary/master/ospd.txt",
            "dwyl_words.txt": "https://raw.githubusercontent.com/dwyl/english-words/master/words_alpha.txt",
            "letterpress.txt": "https://raw.githubusercontent.com/atebits/Words/master/Words/en.txt", 
            "moby_words.txt": "https://raw.githubusercontent.com/words/moby/master/words.txt",
            # Swapped broken crossword link for Google's scraped web corpus
            "google_web_slang.txt": "https://raw.githubusercontent.com/first20hours/google-10000-english/master/20k.txt"
        }

        print("\n[INFO] Synchronizing master dictionary databases...")
        for filename, url in dict_sources.items():
            if not os.path.exists(filename):
                try:
                    urllib.request.urlretrieve(url, filename)
                except Exception as e:
                    print(f"[WARNING] Failed to download {filename}: {e}")
            
            # If the file exists (either just downloaded or already there), read it
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        master_word_list.add(line.strip().upper())
                
        # 3. Load Scrabble 2-letter list
        scrabble_2 = {"AA","AB","AD","AE","AG","AH","AI","AL","AM","AN","AR","AS","AT","AW","AX","AY","BA","BE","BI","BO","BY","DA","DE","DO","ED","EF","EH","EL","EM","EN","ER","ES","ET","EX","FA","FE","GO","HA","HE","HI","HM","HO","ID","IF","IN","IS","IT","JO","KA","KI","LA","LI","LO","MA","ME","MI","MM","MO","MU","MY","NA","NE","NO","NU","OD","OE","OF","OH","OI","OM","ON","OP","OR","OS","OW","OX","OY","PA","PE","PI","PO","QI","RE","SH","SI","SO","TA","TE","TI","TO","UH","UM","UN","UP","US","UT","WE","WO","XI","XU","YA","YE","YO","ZA"}
        master_word_list.update(scrabble_2)

        # 4. Load Custom Whitelist
        if os.path.exists("whitelist.txt"):
            with open("whitelist.txt", "r", encoding='utf-8', errors='ignore') as f:
                for line in f:
                    master_word_list.add(line.strip().upper())
                    
        # 5. Prune Invalid Words based on available letters and constraints
        pool_counts = Counter(self.letter_pool)
        
        for word in master_word_list:
            if not (2 <= len(word) <= 4):
                continue
            if word in self.blacklist:
                continue
                
            word_counts = Counter(word)
            can_build = True
            
            for char, count in word_counts.items():
                if count > pool_counts.get(char, 0):
                    can_build = False
                    break
            
            if can_build:
                self.valid_words.add(word)
                
        print(f"-> Dictionary pruned: {len(self.valid_words)} combined valid words available.")

    # ==========================================
    # 3. RECURSIVE MATRIX ENGINE (DFS) - LAUNCHER
    # ==========================================
    def solve(self):
        self.valid_prefixes = set()
        for word in self.valid_words:
            for i in range(1, len(word) + 1):
                self.valid_prefixes.add(word[:i])

        print("\n[INFO] Engaging Multiprocessing Matrix Search...")
        self.best_score = 0
        self.best_board = None
        
        unique_letters = list(set(self.letter_pool))
        options = [""] + unique_letters
        tasks = []
        pool_str = "".join(self.letter_pool)
        
        for opt0 in options:
            for opt1 in options:
                temp_pool = Counter(self.letter_pool)
                valid = True
                if opt0:
                    temp_pool[opt0] -= 1
                    if temp_pool[opt0] < 0: valid = False
                if opt1:
                    temp_pool[opt1] -= 1
                    if temp_pool[opt1] < 0: valid = False
                    
                if valid:
                    tasks.append((opt0, opt1, pool_str, self.grid_size, self.valid_words, self.valid_prefixes, self.letter_values, self.multipliers))

        total_chunks = len(tasks)
        print(f"[INFO] Search space partitioned into {total_chunks} parallel branches. Crushing data...")

        sys.stdout.write("\n\n")
        
        start_time = time.perf_counter()
        completed_chunks = 0
        
        with concurrent.futures.ProcessPoolExecutor() as executor:
            futures = [executor.submit(solve_chunk, task) for task in tasks]
            
            while completed_chunks < total_chunks:
                done, _ = concurrent.futures.wait(futures, timeout=1.0, return_when=concurrent.futures.FIRST_COMPLETED)
                
                for future in done:
                    score, board = future.result()
                    if score > self.best_score:
                        self.best_score = score
                        self.best_board = board
                    completed_chunks += 1
                    futures.remove(future)
                
                elapsed = time.perf_counter() - start_time
                sys.stdout.write(f"\033[F\033[F\r\033[KRuntime: {elapsed:.0f} seconds\n\r\033[K-> Progress: {completed_chunks} / {total_chunks} branches completed (Best Score so far: {self.best_score})\n")
                sys.stdout.flush()

        print(f"\n[INFO] Matrix search complete in {elapsed:.0f} seconds.")

    # ==========================================
    # 5. OUTPUT & BLACKLIST LOOP
    # ==========================================
    def display_results(self):
        if not self.best_board:
            print("\n[!] No valid board configurations could be found with these letters.")
            return

        print("\n==========================================")
        print("          CHAMPION BOARD FOUND!           ")
        print("==========================================\n")
        
        for r in range(self.grid_size):
            row_str = " | ".join(self.best_board[r][c] if self.best_board[r][c] != "" else " " for c in range(self.grid_size))
            print(f" {row_str} ")
            if r < self.grid_size - 1:
                print("---" * 5)
        
        print("\n--- Word Breakdown ---")
        
        found_words = []
        for r in range(self.grid_size):
            curr_word, curr_coords = "", []
            for c in range(self.grid_size):
                char = self.best_board[r][c]
                if char != "":
                    curr_word += char
                    curr_coords.append((r, c))
                else:
                    if len(curr_word) >= 2: found_words.append({"word": curr_word, "coords": curr_coords})
                    curr_word, curr_coords = "", []
            if len(curr_word) >= 2: found_words.append({"word": curr_word, "coords": curr_coords})

        for c in range(self.grid_size):
            curr_word, curr_coords = "", []
            for r in range(self.grid_size):
                char = self.best_board[r][c]
                if char != "":
                    curr_word += char
                    curr_coords.append((r, c))
                else:
                    if len(curr_word) >= 2: found_words.append({"word": curr_word, "coords": curr_coords})
                    curr_word, curr_coords = "", []
            if len(curr_word) >= 2: found_words.append({"word": curr_word, "coords": curr_coords})

        for item in found_words:
            word = item["word"]
            coords = item["coords"]
            
            word_score = 0
            word_mult_factor = 1
            multiplier_text = ""
            
            for i, (r, c) in enumerate(coords):
                char_score = self.letter_values.get(word[i], 0)
                for mult in self.multipliers:
                    if mult["row"] == r and mult["col"] == c:
                        if mult["type"] == 'L':
                            char_score *= mult["value"]
                            multiplier_text += f" [x{mult['value']} Letter Mult!]"
                        elif mult["type"] == 'W':
                            word_mult_factor *= mult["value"]
                            multiplier_text += f" [x{mult['value']} Word Mult!]"
                word_score += char_score
                
            final_score = word_score * word_mult_factor
            print(f"- {word}: {final_score} pts {multiplier_text}")
            
        used_letters = []
        for r in range(self.grid_size):
            for c in range(self.grid_size):
                if self.best_board[r][c] != "":
                    used_letters.append(self.best_board[r][c])
                    
        pool_counts = Counter(self.letter_pool)
        used_counts = Counter(used_letters)
        
        unused_letters = []
        for char, count in pool_counts.items():
            diff = count - used_counts.get(char, 0)
            if diff > 0:
                unused_letters.extend([char] * diff)
                
        print("----------------------")
        print(f"TOTAL SCORE: {self.best_score} points")
        if unused_letters:
            print(f"UNUSED LETTERS: {', '.join(unused_letters)}\n")
        else:
            print("UNUSED LETTERS: None\n")

    def run_engine_loop(self):
        self.load_and_prompt_letters()
        self.confirm_letter_values()
        self.get_multipliers()
        
        while True:
            self.build_pruned_dictionary()
            self.solve()
            self.display_results()
            
            if not self.best_board:
                break
                
            valid = input("Did the game accept all these words? (Y/N): ").strip().upper()
            if valid == 'Y':
                print("\nExcellent! Puzzle solved.")
                break
            elif valid == 'N':
                bad_words = input("Enter the rejected words, separated by commas: ").strip().upper()
                for w in bad_words.split(','):
                    if w.strip():
                        self.blacklist.add(w.strip())
                
                with open("blacklist.json", 'w') as f:
                    json.dump(list(self.blacklist), f, indent=4)
                    
                print("\n-> Words blacklisted and saved permanently. Recalculating...")
            else:
                print("Please enter Y or N.")

if __name__ == "__main__":
    solver = GridWordSolver()
    solver.run_engine_loop()