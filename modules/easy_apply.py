"""
modules/easy_apply.py
Enhanced Easy Apply with intelligent form filling for additional questions
"""

import time
import json
import os
import re
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
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
        self.question_answers = config.get('question_answers', {})
        
    def _load_applied_jobs(self):
        """Load previously applied jobs from file"""
        if os.path.exists(self.applied_jobs_file):
            try:
                with open(self.applied_jobs_file, 'r') as f:
                    content = f.read().strip()
                    if not content:
                        return []
                    return json.loads(content)
            except json.JSONDecodeError:
                return []
        return []
    
    def _save_applied_job(self, job_info):
        """Save applied job to file"""
        self.applied_jobs.append(job_info)
        with open(self.applied_jobs_file, 'w') as f:
            json.dump(self.applied_jobs, f, indent=2)
    
    def process_job(self, job_element):
        """Process a single job listing - click, check for Easy Apply, and apply"""
        try:
            try:
                self.driver.current_url
            except Exception as e:
                self.logger.error(f"Browser session lost: {str(e)}")
                return False
            
            self._click_with_retry(job_element)
            time.sleep(3)
            
            try:
                self.driver.current_url
            except Exception as e:
                self.logger.error(f"Browser session lost after clicking job: {str(e)}")
                return False
            
            job_info = self._extract_job_info()
            
            if any(j.get('job_id') == job_info.get('job_id') for j in self.applied_jobs):
                self.logger.info(f"Already applied to: {job_info.get('title', 'Unknown')}")
                return False
            
            self.logger.info(f"Job: {job_info.get('title', 'Unknown')} at {job_info.get('company', 'Unknown')}")
            
            if not self._check_easy_apply():
                self.logger.info("Easy Apply not available, skipping...")
                return False
            
            if not self._click_easy_apply():
                self.logger.warning("Could not click Easy Apply button")
                return False
            
            time.sleep(3)
            
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
        """Click element with retry logic"""
        if retries is None:
            retries = self.max_retries
            
        for attempt in range(retries):
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(0.5)
                element.click()
                return True
                
            except ElementClickInterceptedException:
                self.logger.debug(f"Click intercepted, attempt {attempt + 1}/{retries}")
                self._close_overlays()
                time.sleep(1)
                
                try:
                    self.driver.execute_script("arguments[0].click();", element)
                    return True
                except:
                    if attempt == retries - 1:
                        raise
                        
            except StaleElementReferenceException:
                self.logger.debug("Element became stale, retrying...")
                time.sleep(1)
                if attempt == retries - 1:
                    raise
                    
        return False
    
    def _close_overlays(self):
        """Attempt to close any popups or overlays"""
        try:
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
            title_element = self.driver.find_element(
                By.CSS_SELECTOR, 
                "h1.job-details-jobs-unified-top-card__job-title"
            )
            info['title'] = title_element.text
        except:
            info['title'] = "Unknown"
        
        try:
            company_element = self.driver.find_element(
                By.CSS_SELECTOR,
                "a.job-details-jobs-unified-top-card__company-name"
            )
            info['company'] = company_element.text
        except:
            info['company'] = "Unknown"
        
        try:
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
            easy_apply_button = self.driver.find_element(
                By.CSS_SELECTOR,
                "button.jobs-apply-button"
            )
            return "Easy Apply" in easy_apply_button.text
        except NoSuchElementException:
            return False
    
    def _click_easy_apply(self):
        """Click the Easy Apply button"""
        try:
            easy_apply_button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button.jobs-apply-button"))
            )
            self._click_with_retry(easy_apply_button)
            self.logger.info("Clicked Easy Apply button")
            return True
        except Exception as e:
            self.logger.error(f"Error clicking Easy Apply: {str(e)}")
            return False
    
    def _fill_application_form(self):
        """Fill out the multi-step Easy Apply form with intelligent question handling"""
        try:
            wait = WebDriverWait(self.driver, 10)
            
            modal = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, ".jobs-easy-apply-modal")
            ))
            
            step_count = 0
            max_steps = 10
            
            while step_count < max_steps:
                step_count += 1
                self.logger.debug(f"Processing form step {step_count}...")
                
                time.sleep(self.wait_time)
                
                # Fill current form step with intelligent question handling
                self._fill_current_form_fields()
                
                # Check for validation errors
                if self._has_validation_errors():
                    self.logger.warning("Form has validation errors")
                
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
        """Fill all fields in the current form step with intelligent matching"""
        try:
            # Handle text inputs
            self._fill_text_inputs()
            
            # Handle phone numbers
            self._fill_phone_inputs()
            
            # Handle file uploads
            self._fill_file_inputs()
            
            # Handle dropdowns/selects
            self._fill_dropdown_fields()
            
            # Handle radio buttons
            self._handle_radio_buttons()
            
            # Handle checkboxes
            self._handle_checkboxes()
            
            # Handle textareas
            self._fill_textareas()
            
        except Exception as e:
            self.logger.debug(f"Error filling form fields: {str(e)}")
    
    def _fill_text_inputs(self):
        """Fill text input fields with intelligent question matching"""
        try:
            text_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='number']")
            
            for input_field in text_inputs:
                try:
                    if input_field.get_attribute('value'):
                        continue
                    
                    label_text = self._get_field_label(input_field).lower()
                    
                    # Try to match and fill based on label
                    answer = self._match_question_to_answer(label_text)
                    
                    if answer:
                        input_field.clear()
                        input_field.send_keys(str(answer))
                        self.logger.debug(f"Filled '{label_text}' with '{answer}'")
                    
                except Exception as e:
                    self.logger.debug(f"Could not fill text input: {str(e)}")
                    
        except Exception as e:
            self.logger.debug(f"Error in _fill_text_inputs: {str(e)}")
    
    def _fill_phone_inputs(self):
        """Fill phone number fields"""
        try:
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
        except Exception as e:
            self.logger.debug(f"Error filling phone: {str(e)}")
    
    def _fill_file_inputs(self):
        """Handle file uploads (resume/CV)"""
        try:
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
        except Exception as e:
            self.logger.debug(f"Error in file upload: {str(e)}")
    
    def _fill_textareas(self):
        """Fill textarea fields (cover letters, additional info)"""
        try:
            textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
            
            for textarea in textareas:
                try:
                    if textarea.get_attribute('value'):
                        continue
                    
                    label_text = self._get_field_label(textarea).lower()
                    
                    # Generic cover letter or additional info
                    if any(word in label_text for word in ['cover', 'letter', 'why', 'interest', 'additional']):
                        default_text = (
                            "I am excited about this opportunity and believe my skills and experience "
                            "align well with the requirements. I am eager to contribute to your team "
                            "and would welcome the chance to discuss how I can add value."
                        )
                        textarea.send_keys(default_text)
                        self.logger.debug(f"Filled textarea: {label_text}")
                        
                except Exception as e:
                    self.logger.debug(f"Could not fill textarea: {str(e)}")
                    
        except Exception as e:
            self.logger.debug(f"Error filling textareas: {str(e)}")
    
    def _fill_dropdown_fields(self):
        """Handle dropdown/select fields with intelligent matching"""
        try:
            selects = self.driver.find_elements(By.TAG_NAME, "select")
            
            for select in selects:
                try:
                    if select.get_attribute('value'):
                        continue
                    
                    label_text = self._get_field_label(select).lower()
                    
                    # Try to match answer from config
                    answer = self._match_question_to_answer(label_text)
                    
                    if answer:
                        self._select_dropdown_option(select, str(answer))
                    else:
                        # Select first non-empty option as fallback
                        options = select.find_elements(By.TAG_NAME, "option")
                        if len(options) > 1:
                            options[1].click()
                            self.logger.debug(f"Selected default dropdown option for: {label_text}")
                            
                except Exception as e:
                    self.logger.debug(f"Could not fill dropdown: {str(e)}")
                    
        except Exception as e:
            self.logger.debug(f"Error handling dropdowns: {str(e)}")
    
    def _select_dropdown_option(self, select_element, target_value):
        """Select dropdown option by matching value"""
        try:
            select = Select(select_element)
            options = select.options
            
            target_lower = target_value.lower()
            
            # Try exact match first
            for option in options:
                if option.text.lower() == target_lower:
                    select.select_by_visible_text(option.text)
                    self.logger.debug(f"Selected exact match: {option.text}")
                    return True
            
            # Try partial match
            for option in options:
                if target_lower in option.text.lower() or option.text.lower() in target_lower:
                    select.select_by_visible_text(option.text)
                    self.logger.debug(f"Selected partial match: {option.text}")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Error selecting dropdown option: {str(e)}")
            return False
    
    def _handle_radio_buttons(self):
        """Handle radio button groups with intelligent selection"""
        try:
            radio_groups = {}
            radios = self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
            
            for radio in radios:
                name = radio.get_attribute('name')
                if name:
                    if name not in radio_groups:
                        radio_groups[name] = []
                    radio_groups[name].append(radio)
            
            for group_name, buttons in radio_groups.items():
                try:
                    selected = any(btn.is_selected() for btn in buttons)
                    if selected:
                        continue
                    
                    # Get label for this group
                    label_text = self._get_radio_group_label(buttons[0]).lower()
                    
                    # Try to match answer from config
                    answer = self._match_question_to_answer(label_text)
                    
                    if answer:
                        # Try to find matching radio button
                        for btn in buttons:
                            btn_label = self._get_radio_button_label(btn).lower()
                            if str(answer).lower() in btn_label or btn_label in str(answer).lower():
                                btn.click()
                                self.logger.debug(f"Selected radio: {btn_label}")
                                break
                    else:
                        # Select first option as fallback
                        buttons[0].click()
                        self.logger.debug(f"Selected default radio button")
                        
                except Exception as e:
                    self.logger.debug(f"Error with radio group: {str(e)}")
                    
        except Exception as e:
            self.logger.debug(f"Error handling radio buttons: {str(e)}")
    
    def _handle_checkboxes(self):
        """Handle checkboxes intelligently"""
        try:
            checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
            
            for checkbox in checkboxes:
                try:
                    label_text = self._get_field_label(checkbox).lower()
                    
                    # Handle specific checkbox types
                    if any(word in label_text for word in ['agree', 'terms', 'policy', 'consent']):
                        if not checkbox.is_selected():
                            checkbox.click()
                            self.logger.debug(f"Checked: {label_text}")
                    
                except Exception as e:
                    self.logger.debug(f"Could not handle checkbox: {str(e)}")
                    
        except Exception as e:
            self.logger.debug(f"Error handling checkboxes: {str(e)}")
    
    def _match_question_to_answer(self, question_text):
        """Intelligent matching of questions to answers from config"""
        question_lower = question_text.lower()
        qa = self.question_answers
        
        # Years of experience matching
        if 'year' in question_lower and 'experience' in question_lower:
            # Check for specific technology
            for tech, years in qa.get('years_of_experience', {}).items():
                if tech.lower() in question_lower:
                    return years
            # Return default if no specific match
            return qa.get('years_of_experience', {}).get('default', '2')
        
        # Sponsorship related
        if 'sponsor' in question_lower or 'visa' in question_lower:
            if 'require' in question_lower:
                return qa.get('require_visa_sponsorship', 'No')
            return qa.get('sponsorship_required', 'No')
        
        # Work authorization
        if 'authorized' in question_lower or 'authorization' in question_lower:
            return qa.get('authorized_to_work', 'Yes')
        
        # Relocation
        if 'relocat' in question_lower:
            return qa.get('willing_to_relocate', 'Yes')
        
        # Notice period
        if 'notice' in question_lower or 'availability' in question_lower:
            return qa.get('notice_period', 'Immediate')
        
        # Salary expectations
        if 'salary' in question_lower or 'compensation' in question_lower:
            if 'expect' in question_lower or 'desired' in question_lower:
                return qa.get('expected_salary', '')
            if 'current' in question_lower:
                return qa.get('current_salary', '')
        
        # Remote work
        if 'remote' in question_lower:
            return qa.get('comfortable_working_remotely', 'Yes')
        
        # Education
        if 'education' in question_lower or 'degree' in question_lower:
            return qa.get('education_level', "Bachelor's Degree")
        
        # Citizenship
        if 'citizen' in question_lower:
            return qa.get('citizenship_status', 'Authorized to work')
        
        # Gender
        if 'gender' in question_lower:
            return qa.get('gender', 'Prefer not to say')
        
        # Veteran status
        if 'veteran' in question_lower:
            return qa.get('veteran_status', 'I am not a protected veteran')
        
        # Disability
        if 'disabilit' in question_lower:
            return qa.get('disability_status', "I don't wish to answer")
        
        # Race/Ethnicity
        if 'race' in question_lower or 'ethnicity' in question_lower:
            return qa.get('race_ethnicity', 'Prefer not to say')
        
        # Proficiency level
        if 'proficien' in question_lower:
            return qa.get('proficiency_level', 'Expert')
        
        # How did you hear about us
        if 'hear about' in question_lower or 'how did you' in question_lower:
            return qa.get('how_did_you_hear', 'LinkedIn')
        
        # Website/links
        if 'linkedin' in question_lower or 'profile' in question_lower:
            return qa.get('websites', {}).get('linkedin', '')
        if 'github' in question_lower:
            return qa.get('websites', {}).get('github', '')
        if 'portfolio' in question_lower or 'website' in question_lower:
            return qa.get('websites', {}).get('portfolio', '')
        
        # Email
        if 'email' in question_lower or 'e-mail' in question_lower:
            return self.config['personal_info'].get('email', '')
        
        # Phone
        if 'phone' in question_lower:
            return self.config['personal_info'].get('phone', '')
        
        # Name fields
        if 'first name' in question_lower:
            return self.config['personal_info'].get('first_name', '')
        if 'last name' in question_lower or 'surname' in question_lower:
            return self.config['personal_info'].get('last_name', '')
        
        return None
    
    def _get_field_label(self, element):
        """Get the label text for an input field"""
        try:
            # Try by for/id relationship
            field_id = element.get_attribute('id')
            if field_id:
                try:
                    label = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{field_id}']")
                    return label.text
                except:
                    pass
            
            # Try parent label
            try:
                parent = element.find_element(By.XPATH, "..")
                if parent.tag_name == "label":
                    return parent.text
            except:
                pass
            
            # Try aria-label
            aria_label = element.get_attribute('aria-label')
            if aria_label:
                return aria_label
            
            # Try placeholder
            placeholder = element.get_attribute('placeholder')
            if placeholder:
                return placeholder
            
            # Try name attribute
            name = element.get_attribute('name')
            if name:
                return name
            
        except Exception as e:
            self.logger.debug(f"Could not get field label: {str(e)}")
        
        return ""
    
    def _get_radio_group_label(self, radio_button):
        """Get label for radio button group"""
        try:
            # Try fieldset legend
            fieldset = radio_button.find_element(By.XPATH, "./ancestor::fieldset")
            legend = fieldset.find_element(By.TAG_NAME, "legend")
            return legend.text
        except:
            return self._get_field_label(radio_button)
    
    def _get_radio_button_label(self, radio_button):
        """Get individual radio button label"""
        return self._get_field_label(radio_button)
    
    def _has_validation_errors(self):
        """Check if form has validation errors"""
        try:
            errors = self.driver.find_elements(
                By.CSS_SELECTOR,
                ".artdeco-inline-feedback--error, .fb-form-element-error"
            )
            return len(errors) > 0
        except:
            return False
    
    def _click_form_navigation_button(self):
        """Click the appropriate navigation button (Next, Review, Submit)"""
        try:
            # Try Submit button first
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
            close_buttons = self.driver.find_elements(
                By.XPATH,
                "//button[@aria-label='Dismiss']"
            )
            
            for btn in close_buttons:
                if btn.is_displayed():
                    btn.click()
                    time.sleep(1)
                    
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