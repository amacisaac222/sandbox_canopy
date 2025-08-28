"""
Simple company management stub for testing
"""

class CompanyManager:
    def __init__(self):
        self.companies = {}
    
    def get_company(self, company_id):
        return self.companies.get(company_id)
    
    def create_company(self, name, description=""):
        company_id = len(self.companies) + 1
        company = {
            "id": company_id,
            "name": name,
            "description": description
        }
        self.companies[company_id] = company
        return company

# Global instance
company_manager = CompanyManager()