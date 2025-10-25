"""
modules/easy_apply.py
Handles the Easy Apply process with multi-step form support and intelligent question answering
"""

import time
import json
import os
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    ElementClickInterceptedException,
    StaleElementReferenceException
)

class EasyApplyBot:
    def __init__(self, driver, config, logger):
        self.driver = driver
        self.config = config
        self.logger = logger
        self.wait_time = config['automation_settings'].get('wait_time', 3)
        self.max_retries = config['automation_settings'].get('max_retries', 3)
        self.applied_jobs_file = config.get('applied_jobs_log', 'applied_jobs.json')
        self.applied_jobs = self._load_applied_jobs()
        
    def _load_applied_jobs(self):
        """Load previously applied jobs from file"""
        if os.path.exists(self.applied_jobs_file):
            try:
                with open(self.applied_jobs_file, 'r') as f:
                    content = f.read().strip()
                    if not content:  # File is empty
                        return []
                    return json.loads(content)
            except json.JSONDecodeError:
                # File is corrupted, start fresh
                return []
        return []
    
    def _save_applied_job(self, job_info):
        """Save applied job to file"""
        self.applied_jobs.append(job_info)
        with open(self.applied_jobs_file, 'w') as f:
            json.dump(self.applied_jobs, f, indent=2)
    
    def process_job(self, job_element):
        """
        Process a single job listing - click, check for Easy Apply, and apply
        Returns True if successfully applied, False otherwise
        """
        try:
            # Check if browser is still alive
            try:
                self.driver.current_url
            except Exception as e:
                self.logger.error(f"Browser session lost: {str(e)}")
                return False
            
            # Click on the job card
            self._click_with_retry(job_element)
            time.sleep(0.8)  # Reduced for speed
            
            # Check if browser is still alive after click
            try:
                self.driver.current_url
            except Exception as e:
                self.logger.error(f"Browser session lost after clicking job: {str(e)}")
                return False
            
            # Get job details
            job_info = self._extract_job_info()
            
            # Check if already applied
            if any(j.get('job_id') == job_info.get('job_id') for j in self.applied_jobs):
                self.logger.info(f"Already applied to: {job_info.get('title', 'Unknown')}")
                return False
            
            self.logger.info(f"Job: {job_info.get('title', 'Unknown')} at {job_info.get('company', 'Unknown')}")
            
            # Check for Easy Apply button
            if not self._check_easy_apply():
                self.logger.info("Easy Apply not available, skipping...")
                return False
            
            # Click Easy Apply
            if not self._click_easy_apply():
                self.logger.warning("Could not click Easy Apply button")
                return False
            
            time.sleep(1)  # Reduced for speed
            
            # Fill multi-step form
            if self._fill_application_form():
                job_info['applied_at'] = datetime.now().isoformat()
                self._save_applied_job(job_info)
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Error processing job: {str(e)}", exc_info=True)
            return False
    
    def _click_with_retry(self, element, retries=None):
        """Click element with retry logic for intercepted clicks"""
        if retries is None:
            retries = self.max_retries
            
        for attempt in range(retries):
            try:
                # Scroll element into view
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(0.3)  # Reduced for speed
                
                # Try JavaScript click first (faster and more reliable)
                try:
                    self.driver.execute_script("arguments[0].click();", element)
                    return True
                except:
                    pass
                
                # Fallback to regular click
                element.click()
                return True
                
            except ElementClickInterceptedException:
                self.logger.debug(f"Click intercepted, attempt {attempt + 1}/{retries}")
                
                # Try to close any overlays
                self._close_overlays()
                time.sleep(0.5)
                
                # Try JavaScript click again
                try:
                    self.driver.execute_script("arguments[0].click();", element)
                    return True
                except:
                    if attempt == retries - 1:
                        raise
                        
            except StaleElementReferenceException:
                self.logger.debug("Element became stale, retrying...")
                time.sleep(0.5)
                if attempt == retries - 1:
                    raise
                    
        return False
    
    def _close_overlays(self):
        """Attempt to close any popups or overlays"""
        try:
            # Common overlay close button selectors
            close_selectors = [
                "button[aria-label='Dismiss']",
                "button[data-test-modal-close-btn]",
                ".artdeco-modal__dismiss",
                "button.msg-overlay-bubble-header__control"
            ]
            
            for selector in close_selectors:
                try:
                    close_btn = self.driver.find_element(By.CSS_SELECTOR, selector)
                    close_btn.click()
                    self.logger.debug("Closed an overlay")
                    time.sleep(0.5)
                except:
                    pass
                    
        except Exception as e:
            self.logger.debug(f"No overlays to close: {str(e)}")
    
    def _extract_job_info(self):
        """Extract job information from the current job view"""
        info = {}
        
        try:
            # Job title
            title_element = self.driver.find_element(
                By.CSS_SELECTOR, 
                "h1.job-details-jobs-unified-top-card__job-title"
            )
            info['title'] = title_element.text
        except:
            info['title'] = "Unknown"
        
        try:
            # Company name
            company_element = self.driver.find_element(
                By.CSS_SELECTOR,
                "a.job-details-jobs-unified-top-card__company-name"
            )
            info['company'] = company_element.text
        except:
            info['company'] = "Unknown"
        
        try:
            # Job ID from URL
            current_url = self.driver.current_url
            if "currentJobId=" in current_url:
                job_id = current_url.split("currentJobId=")[1].split("&")[0]
                info['job_id'] = job_id
        except:
            info['job_id'] = None
        
        info['url'] = self.driver.current_url
        
        return info
    
    def _check_easy_apply(self):
        """Check if Easy Apply button exists"""
        try:
            # Quick check with multiple selectors
            button_selectors = [
                "button.jobs-apply-button",
                "button[aria-label*='Easy Apply']",
                ".jobs-apply-button--top-card button"
            ]
            
            for selector in button_selectors:
                try:
                    buttons = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for button in buttons:
                        if button.is_displayed() and "Easy Apply" in button.text:
                            return True
                except:
                    continue
            
            return False
        except:
            return False
    
    def _click_easy_apply(self):
        """Click the Easy Apply button"""
        try:
            # Multiple selectors for Easy Apply button
            button_selectors = [
                "button.jobs-apply-button",
                "button[aria-label*='Easy Apply']",
                ".jobs-apply-button--top-card button"
            ]
            
            for selector in button_selectors:
                try:
                    easy_apply_button = WebDriverWait(self.driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    
                    # Use JavaScript click for speed
                    self.driver.execute_script("arguments[0].click();", easy_apply_button)
                    self.logger.info("Clicked Easy Apply button")
                    return True
                except:
                    continue
            
            self.logger.warning("Could not find Easy Apply button")
            return False
            
        except Exception as e:
            self.logger.error(f"Error clicking Easy Apply: {str(e)}")
            return False
    
    def _fill_application_form(self):
        """
        Fill out the multi-step Easy Apply form
        Handles dynamic fields and multiple steps
        """
        try:
            wait = WebDriverWait(self.driver, 10)
            
            # Wait for modal to appear
            modal = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".jobs-easy-apply-modal")
            ))
            
            step_count = 0
            max_steps = 10  # Safety limit
            
            while step_count < max_steps:
                step_count += 1
                self.logger.debug(f"Processing form step {step_count}...")
                
                time.sleep(1.5)  # Reduced for speed
                
                # Fill current form step
                self._fill_current_form_fields()
                
                # Check what buttons are available
                button_clicked = self._click_form_navigation_button()
                
                if button_clicked == "submitted":
                    self.logger.info("✓ Application submitted successfully!")
                    time.sleep(2)
                    self._close_success_modal()
                    return True
                elif button_clicked == "next":
                    self.logger.debug("Moved to next step")
                    continue
                elif button_clicked == "review":
                    self.logger.debug("Reviewing application")
                    continue
                else:
                    # Could not find appropriate button
                    self.logger.warning("Could not find next/submit button, discarding application")
                    self._discard_application()
                    return False
            
            self.logger.warning("Exceeded maximum form steps")
            self._discard_application()
            return False
            
        except Exception as e:
            self.logger.error(f"Error filling application form: {str(e)}")
            self._discard_application()
            return False
    
    def _fill_current_form_fields(self):
        """Fill all fields in the current form step with intelligent question answering"""
        try:
            # Handle text input fields with smart question answering
            text_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='number']")
            
            for input_field in text_inputs:
                try:
                    # Check if field is empty
                    if not input_field.get_attribute('value'):
                        label = self._get_field_label(input_field)
                        self._fill_field_intelligently(input_field, label)
                except Exception as e:
                    self.logger.debug(f"Could not fill input field: {str(e)}")
            
            # Handle textarea fields (for longer answers)
            textareas = self.driver.find_elements(By.CSS_SELECTOR, "textarea")
            for textarea in textareas:
                try:
                    if not textarea.get_attribute('value'):
                        label = self._get_field_label(textarea)
                        self._fill_field_intelligently(textarea, label)
                except:
                    pass
            
            # Handle phone number fields
            phone_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='tel']")
            for phone_input in phone_inputs:
                try:
                    if not phone_input.get_attribute('value'):
                        phone_input.clear()
                        phone = self.config['personal_info']['phone']
                        phone_input.send_keys(phone)
                        self.logger.debug("Filled phone number")
                except:
                    pass
            
            # Handle file uploads (resume)
            file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
            for file_input in file_inputs:
                try:
                    resume_path = self.config['personal_info'].get('resume_path')
                    if resume_path and os.path.exists(resume_path):
                        abs_path = os.path.abspath(resume_path)
                        file_input.send_keys(abs_path)
                        self.logger.debug("Uploaded resume")
                        time.sleep(2)
                except Exception as e:
                    self.logger.debug(f"Could not upload file: {str(e)}")
            
            # Handle dropdowns/select fields
            self._fill_dropdown_fields()
            
            # Handle radio buttons (default to first option if nothing selected)
            self._handle_radio_buttons()
            
        except Exception as e:
            self.logger.debug(f"Error filling form fields: {str(e)}")
    
    def _get_field_label(self, input_field):
        """Get the label text for an input field"""
        try:
            field_id = input_field.get_attribute('id')
            if field_id:
                label = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{field_id}']")
                return label.text.lower()
        except:
            pass
        
        # Try to find label by looking at parent elements
        try:
            parent = input_field.find_element(By.XPATH, "..")
            label_element = parent.find_element(By.TAG_NAME, "label")
            return label_element.text.lower()
        except:
            pass
        
        return ""
    
    def _fill_field_intelligently(self, field, label_text):
        """
        Intelligently fill fields based on question text
        Handles experience questions, yes/no questions, etc.
        """
        try:
            label = label_text.lower()
            qa_config = self.config.get('question_answers', {})
            
            # Experience questions (e.g., "How many years of experience in Java?")
            if 'year' in label and 'experience' in label:
                answer = self._get_experience_answer(label, qa_config)
                if answer:
                    field.clear()
                    field.send_keys(answer)
                    self.logger.info(f"Filled experience question: {answer} years")
                    return
            
            # Sponsorship questions
            if 'sponsor' in label or 'visa' in label:
                answer = qa_config.get('require_visa_sponsorship', 'No')
                field.clear()
                field.send_keys(answer)
                self.logger.info(f"Filled sponsorship: {answer}")
                return
            
            # Relocation questions
            if 'relocate' in label or 'relocation' in label:
                answer = qa_config.get('willing_to_relocate', 'Yes')
                field.clear()
                field.send_keys(answer)
                self.logger.info(f"Filled relocation: {answer}")
                return
            
            # Notice period
            if 'notice' in label:
                answer = qa_config.get('notice_period', 'Immediate')
                field.clear()
                field.send_keys(answer)
                self.logger.info(f"Filled notice period: {answer}")
                return
            
            # Salary questions
            if 'salary' in label or 'compensation' in label:
                if 'expect' in label or 'desired' in label:
                    answer = qa_config.get('expected_salary', '800000')
                else:
                    answer = qa_config.get('current_salary', '600000')
                field.clear()
                field.send_keys(answer)
                self.logger.info(f"Filled salary: {answer}")
                return
            
            # Authorization to work
            if 'authorized' in label or 'authorization' in label:
                answer = qa_config.get('authorized_to_work', 'Yes')
                field.clear()
                field.send_keys(answer)
                self.logger.info(f"Filled authorization: {answer}")
                return
            
            # Remote work
            if 'remote' in label:
                answer = qa_config.get('comfortable_working_remotely', 'Yes')
                field.clear()
                field.send_keys(answer)
                self.logger.info(f"Filled remote work: {answer}")
                return
            
            # Website/LinkedIn/GitHub
            if 'website' in label or 'linkedin' in label or 'github' in label or 'portfolio' in label:
                websites = qa_config.get('websites', {})
                if 'linkedin' in label:
                    answer = websites.get('linkedin', '')
                elif 'github' in label:
                    answer = websites.get('github', '')
                else:
                    answer = websites.get('portfolio', '')
                
                if answer:
                    field.clear()
                    field.send_keys(answer)
                    self.logger.info(f"Filled website field")
                return
            
            # Fallback to basic field filling
            self._fill_field_by_label(field, label)
                
        except Exception as e:
            self.logger.debug(f"Error in intelligent field filling: {str(e)}")
    
    def _get_experience_answer(self, question, qa_config):
        """
        Extract experience answer based on technology mentioned in question
        E.g., "How many years of Java experience?" -> looks for 'java' in config
        """
        try:
            experience_config = qa_config.get('years_of_experience', {})
            
            # Check for specific technologies
            technologies = ['python', 'java', 'javascript', 'react', 'node', 'angular', 
                          'vue', 'sql', 'aws', 'azure', 'gcp', 'docker', 'kubernetes',
                          'c++', 'c#', 'ruby', 'php', 'golang', 'rust', 'swift',
                          'machine learning', 'data science', 'deep learning', 'ai']
            
            for tech in technologies:
                if tech in question:
                    if tech in experience_config:
                        return str(experience_config[tech])
            
            # Return default experience if no specific tech found
            return str(experience_config.get('default', '2'))
            
        except:
            return '2'  # Default fallback
    
    def _fill_field_by_label(self, input_field, label):
        """Fill field based on its label"""
        try:
            config_info = self.config['personal_info']
            
            if 'email' in label or 'e-mail' in label:
                input_field.clear()
                input_field.send_keys(config_info['email'])
                self.logger.debug("Filled email field")
            elif 'phone' in label:
                input_field.clear()
                input_field.send_keys(config_info['phone'])
                self.logger.debug("Filled phone field")
            elif 'first name' in label:
                input_field.clear()
                input_field.send_keys(config_info.get('first_name', 'John'))
                self.logger.debug("Filled first name")
            elif 'last name' in label:
                input_field.clear()
                input_field.send_keys(config_info.get('last_name', 'Doe'))
                self.logger.debug("Filled last name")
                
        except Exception as e:
            self.logger.debug(f"Could not fill field by label: {str(e)}")
    
    def _fill_dropdown_fields(self):
        """Handle dropdown/select fields"""
        try:
            # Find all select dropdowns
            selects = self.driver.find_elements(By.TAG_NAME, "select")
            
            for select in selects:
                try:
                    # If nothing is selected, select first valid option
                    if not select.get_attribute('value'):
                        options = select.find_elements(By.TAG_NAME, "option")
                        if len(options) > 1:  # Skip if only placeholder
                            options[1].click()
                            self.logger.debug("Selected dropdown option")
                except:
                    pass
        except Exception as e:
            self.logger.debug(f"Error handling dropdowns: {str(e)}")
    
    def _handle_radio_buttons(self):
        """Handle radio button groups"""
        try:
            # Find all radio button groups
            radio_groups = {}
            radios = self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
            
            for radio in radios:
                name = radio.get_attribute('name')
                if name:
                    if name not in radio_groups:
                        radio_groups[name] = []
                    radio_groups[name].append(radio)
            
            # For each group, if none selected, select first
            for group_name, buttons in radio_groups.items():
                try:
                    selected = any(btn.is_selected() for btn in buttons)
                    if not selected and buttons:
                        buttons[0].click()
                        self.logger.debug(f"Selected radio button for {group_name}")
                except:
                    pass
                    
        except Exception as e:
            self.logger.debug(f"Error handling radio buttons: {str(e)}")
    
    def _click_form_navigation_button(self):
        """
        Click the appropriate navigation button (Next, Review, Submit)
        Returns: 'next', 'review', 'submitted', or None
        """
        try:
            # Try to find Submit button first
            submit_buttons = self.driver.find_elements(
                By.XPATH, 
                "//button[contains(@aria-label, 'Submit') or contains(text(), 'Submit')]"
            )
            
            for btn in submit_buttons:
                if btn.is_displayed() and btn.is_enabled():
                    self._click_with_retry(btn)
                    self.logger.debug("Clicked Submit button")
                    return "submitted"
            
            # Try Review button
            review_buttons = self.driver.find_elements(
                By.XPATH,
                "//button[contains(@aria-label, 'Review') or contains(text(), 'Review')]"
            )
            
            for btn in review_buttons:
                if btn.is_displayed() and btn.is_enabled():
                    self._click_with_retry(btn)
                    self.logger.debug("Clicked Review button")
                    return "review"
            
            # Try Next button
            next_buttons = self.driver.find_elements(
                By.XPATH,
                "//button[contains(@aria-label, 'Next') or contains(text(), 'Next')]"
            )
            
            for btn in next_buttons:
                if btn.is_displayed() and btn.is_enabled():
                    self._click_with_retry(btn)
                    self.logger.debug("Clicked Next button")
                    return "next"
            
            # Try Continue button
            continue_buttons = self.driver.find_elements(
                By.XPATH,
                "//button[contains(@aria-label, 'Continue') or contains(text(), 'Continue')]"
            )
            
            for btn in continue_buttons:
                if btn.is_displayed() and btn.is_enabled():
                    self._click_with_retry(btn)
                    self.logger.debug("Clicked Continue button")
                    return "next"
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error clicking navigation button: {str(e)}")
            return None
    
    def _discard_application(self):
        """Discard the current application"""
        try:
            # Try to find and click dismiss/close button
            close_buttons = self.driver.find_elements(
                By.XPATH,
                "//button[@aria-label='Dismiss']"
            )
            
            for btn in close_buttons:
                if btn.is_displayed():
                    btn.click()
                    time.sleep(1)
                    
                    # Confirm discard if prompted
                    try:
                        discard_btn = self.driver.find_element(
                            By.XPATH,
                            "//button[contains(@data-control-name, 'discard')]"
                        )
                        discard_btn.click()
                        self.logger.debug("Discarded application")
                    except:
                        pass
                    break
                    
        except Exception as e:
            self.logger.debug(f"Error discarding application: {str(e)}")
    
    def _close_success_modal(self):
        """Close the success confirmation modal"""
        try:
            time.sleep(2)
            close_btn = self.driver.find_element(
                By.XPATH,
                "//button[@aria-label='Dismiss']"
            )
            close_btn.click()
            self.logger.debug("Closed success modal")
        except:
            pass