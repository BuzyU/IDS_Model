import pandas as pd
import numpy as np
import re
import csv
import io
import os
import logging
from docx import Document
import nltk
from nltk.corpus import words
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class DataProcessor:
    def __init__(self):
        self.data = None
        self.original_data = None
        self.file_type = None
        self.corrections = defaultdict(list)
        self.removed_rows = []
        
        # Download NLTK resources if not already present
        try:
            nltk.data.find('corpora/words')
        except LookupError:
            nltk.download('words')
        
        # Load English word list
        self.english_words = set(words.words())
        
    def load_file(self, file_path, file_extension):
        """Load file based on its extension"""
        self.file_type = file_extension
        
        try:
            if file_extension in ['csv']:
                self.data = pd.read_csv(file_path)
            elif file_extension in ['xlsx', 'xls']:
                self.data = pd.read_excel(file_path)
            elif file_extension in ['docx']:
                doc = Document(file_path)
                # Extract text and convert to a dataframe
                text = [p.text for p in doc.paragraphs if p.text.strip()]
                self.data = pd.DataFrame(text, columns=['Content'])
            elif file_extension in ['doc']:
                # For .doc files, we'll create a simple text extraction
                # (Note: full .doc support would require additional libraries)
                with open(file_path, 'rb') as file:
                    content = file.read().decode('utf-8', errors='ignore')
                lines = content.split('\n')
                self.data = pd.DataFrame(lines, columns=['Content'])
            elif file_extension in ['txt']:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                    lines = file.readlines()
                self.data = pd.DataFrame(lines, columns=['Content'])
            else:
                raise ValueError(f"Unsupported file type: {file_extension}")
            
            # Store original data for comparison
            self.original_data = self.data.copy()
            
            logger.debug(f"File loaded successfully: {file_path}")
            
        except Exception as e:
            logger.error(f"Error loading file: {str(e)}")
            raise ValueError(f"Could not process the file: {str(e)}")
    
    def clean_data(self):
        """Clean and refine the data"""
        if self.data is None:
            raise ValueError("No data loaded. Please load a file first.")
        
        try:
            # 1. Handle missing values - first track them for reporting
            null_indices = self.data.isnull().any(axis=1)
            self.removed_rows = self.data[null_indices].index.tolist()
            
            # 2. Remove rows with missing values
            self.data = self.data.dropna()
            
            # 3. Fix spelling errors in string columns
            for column in self.data.select_dtypes(include=['object']).columns:
                self.data[column] = self.data[column].apply(
                    lambda x: self._fix_spelling(x, column) if isinstance(x, str) else x
                )
            
            # 4. Strip whitespace from string values
            for column in self.data.select_dtypes(include=['object']).columns:
                self.data[column] = self.data[column].apply(
                    lambda x: x.strip() if isinstance(x, str) else x
                )
            
            # 5. Convert date strings to datetime objects where possible
            for column in self.data.select_dtypes(include=['object']).columns:
                try:
                    # Check if the column contains date-like strings
                    if self.data[column].str.match(r'\d{1,4}[-/]\d{1,2}[-/]\d{1,4}').any():
                        self.data[column] = pd.to_datetime(self.data[column], errors='ignore')
                except:
                    continue
                    
            logger.debug("Data cleaning completed successfully")
            
        except Exception as e:
            logger.error(f"Error cleaning data: {str(e)}")
            raise RuntimeError(f"Error during data cleaning: {str(e)}")
    
    def _fix_spelling(self, text, column_name):
        """Fix spelling errors in text"""
        if not text or not isinstance(text, str):
            return text
            
        # Split text into words
        words = re.findall(r'\b\w+\b', text)
        corrected_text = text
        
        for word in words:
            # Only check words of reasonable length that are alphabetic
            if len(word) >= 3 and word.isalpha() and word.lower() not in self.english_words:
                # Simple spelling correction - check for similar words
                # For a more sophisticated approach, you could use libraries like pyspellchecker
                suggested_word = self._get_closest_word(word.lower())
                
                if suggested_word and suggested_word != word.lower():
                    # Replace the word with proper case matching
                    if word.isupper():
                        replacement = suggested_word.upper()
                    elif word[0].isupper():
                        replacement = suggested_word.capitalize()
                    else:
                        replacement = suggested_word
                        
                    # Track the correction
                    self.corrections[column_name].append((word, replacement))
                    
                    # Replace in the text (respecting word boundaries)
                    corrected_text = re.sub(r'\b' + re.escape(word) + r'\b', replacement, corrected_text)
        
        return corrected_text
    
    def _get_closest_word(self, word):
        """Get the closest matching word from dictionary"""
        # This is a simplified approach - in a production environment,
        # you might want to use more sophisticated algorithms or libraries
        
        # Check common typos with simple transformations
        candidates = []
        
        # 1. Check for repeated letters
        candidates.append(re.sub(r'(.)\1+', r'\1', word))
        
        # 2. Try removing one letter
        for i in range(len(word)):
            candidates.append(word[:i] + word[i+1:])
        
        # 3. Try swapping adjacent letters
        for i in range(len(word)-1):
            candidates.append(word[:i] + word[i+1] + word[i] + word[i+2:])
        
        # Look for matches in our word list
        for candidate in candidates:
            if candidate in self.english_words:
                return candidate
                
        return None  # No close match found
    
    def save_file(self, output_path):
        """Save processed data to a file"""
        if self.data is None:
            raise ValueError("No data to save. Please process a file first.")
        
        try:
            file_extension = os.path.splitext(output_path)[1].lower()[1:]
            
            if file_extension in ['csv']:
                self.data.to_csv(output_path, index=False)
            elif file_extension in ['xlsx', 'xls']:
                self.data.to_excel(output_path, index=False)
            elif file_extension in ['txt']:
                if 'Content' in self.data.columns:
                    with open(output_path, 'w', encoding='utf-8') as f:
                        for line in self.data['Content']:
                            f.write(f"{line}\n")
                else:
                    self.data.to_csv(output_path, index=False, sep='\t')
            else:
                # Default to CSV for unsupported export formats
                self.data.to_csv(output_path, index=False)
                
            logger.debug(f"File saved successfully: {output_path}")
            
        except Exception as e:
            logger.error(f"Error saving file: {str(e)}")
            raise RuntimeError(f"Could not save the file: {str(e)}")
    
    def get_stats(self):
        """Get statistics about the current data"""
        if self.data is None:
            return {}
            
        stats = {
            'row_count': len(self.data),
            'column_count': len(self.data.columns),
            'columns': list(self.data.columns),
            'dtypes': {col: str(dtype) for col, dtype in self.data.dtypes.items()},
            'null_counts': {col: int(count) for col, count in self.data.isnull().sum().items() if count > 0}
        }
        
        return stats
    
    def get_corrections(self):
        """Get list of spelling corrections made"""
        return dict(self.corrections)
    
    def get_removed_rows(self):
        """Get information about removed rows"""
        return self.removed_rows
