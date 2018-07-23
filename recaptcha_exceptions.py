"""
Exceptions that can thrown while running the recaptcha solver    
"""

class RecaptchaNotFoundException(Exception):
    """
    Thrown when the recaptcha box doesn't exist or can't be detected
    """
    pass

class ElementNotFoundException(Exception):
    """
    Thrown when a recaptcha element cannot be found
    """
    pass    

class AccessDeniedException(Exception):
    """
    Thrown when recaptcha detects too many automated responses
    and denies access
    """
    pass 
