"""
tools package - LangChain tool sets for each department agent.
"""

from tools.finance_tools import FINANCE_TOOLS, set_db as finance_set_db
from tools.hr_tools import HR_TOOLS, set_db as hr_set_db
from tools.sales_tools import SALES_TOOLS, set_db as sales_set_db
from tools.operations_tools import OPERATIONS_TOOLS, set_db as ops_set_db

__all__ = [
    "FINANCE_TOOLS",
    "HR_TOOLS",
    "SALES_TOOLS",
    "OPERATIONS_TOOLS",
    "finance_set_db",
    "hr_set_db",
    "sales_set_db",
    "ops_set_db",
]
