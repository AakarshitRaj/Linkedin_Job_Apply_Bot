"""
modules/config_manager.py
Handles loading and validating configuration from JSON file
"""

import json
import os
from pathlib import Path

class ConfigManager:
    def __init__(self, config_path='config.json'):
        self.config_path = config_path
        
    def load_config(self):
        """Load configuration from JSON file"""
        if not os.path.exists(self.config_path):
            self._create_default_config()
            raise FileNotFoundError(
                f"Config file not found. A template has been created at {self.config_path}. "
                "Please fill in your details and run again."
            )
        
        with open(self.config_path, 'r') as f:
            config = json.load(f)
        
        self._validate_config(config)
        return config
    
    def _create_default_config(self):
        """Create a default configuration template"""
        default_config = {
            "linkedin_credentials": {
                "email": "your_email@example.com",
                "password": "your_password"
            },
            "personal_info": {
                "email": "your_email@example.com",
                "phone": "1234567890",
                "country_code": "+1",
                "first_name": "John",
                "last_name": "Doe",
                "resume_path": "path/to/your/resume.pdf"
            },
            "job_search": {
                "keywords": ["Data Scientist", "Machine Learning Engineer"],
                "location": "United States",
                "date_posted": "Past Week",
                "experience_level": ["Entry level", "Associate"],
                "max_jobs": 50
            },
            "automation_settings": {
                "wait_time": 3,
                "max_retries": 3,
                "scroll_pause": 2,
                "headless": False
            },
            "question_answers": {
                "years_of_experience": {
                    "default": "2",
                    "python": "3",
                    "java": "2",
                    "javascript": "2",
                    "react": "1",
                    "node": "1",
                    "sql": "2",
                    "aws": "1"
                },
                "sponsorship_required": "No",
                "willing_to_relocate": "Yes",
                "notice_period": "Immediate",
                "expected_salary": "60000",
                "current_salary": "50000",
                "citizenship_status": "Authorized to work",
                "gender": "Prefer not to say",
                "veteran_status": "I am not a protected veteran",
                "disability_status": "I don't wish to answer",
                "race_ethnicity": "Prefer not to say",
                "authorized_to_work": "Yes",
                "require_visa_sponsorship": "No",
                "comfortable_working_remotely": "Yes",
                "years_in_current_role": "2",
                "education_level": "Bachelor's Degree",
                "proficiency_level": "Expert",
                "how_did_you_hear": "LinkedIn"
            },
            "applied_jobs_log": "applied_jobs.json"
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(default_config, f, indent=4)
    
    def _validate_config(self, config):
        """Validate that required configuration fields exist"""
        required_fields = [
            'linkedin_credentials',
            'personal_info',
            'job_search',
            'automation_settings'
        ]
        
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required configuration field: {field}")
        
        # Validate resume path exists
        resume_path = config['personal_info'].get('resume_path')
        if resume_path and not os.path.exists(resume_path):
            raise FileNotFoundError(f"Resume file not found at: {resume_path}")
        
        return True