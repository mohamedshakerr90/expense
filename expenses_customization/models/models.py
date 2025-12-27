# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging
_log = logging.getLogger(__name__)


class LocationNumbers(models.Model):
    _name = 'location.numbers'
    name = fields.Char('Location Number')
    

class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    location_numbers_ids = fields.Many2many('location.numbers', string='Location Numbers')
    approve_employee = fields.Many2one('hr.employee', string='Approved By')
    approve_user = fields.Many2one('res.users', string='Approved User By', related='approve_employee.user_id', readonly=True, store=True)


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'
    expense_journal_id = fields.Many2one(
        "account.journal",
        string="Expense Journal",
        related='employee_id.expense_journal_id',
        store=True,
        help="The Employee's default journal used when an employee expense is created.",
    )
    expense_payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        string="Payment methods for Expense",
        related='employee_id.expense_payment_method_line_id',
        store=True,
    )

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    analytic_account_ids = fields.Many2many('account.analytic.account', string='Analytic Accounts')
    expense_journal_id = fields.Many2one(
        "account.journal",
        string="Expense Journal",
        help="The Employee's default journal used when an employee expense is created.",
    )
    expense_payment_method_line_id = fields.Many2one(
        "account.payment.method.line",
        string="Payment methods for Expense",
        readonly=True,
    )
    @api.onchange('expense_journal_id')
    def onchange_expense_journal_id(self):
        if self.expense_journal_id and self.expense_journal_id.outbound_payment_method_line_ids:
            self.expense_payment_method_line_id = self.expense_journal_id.outbound_payment_method_line_ids.ids[0]
        else:
            self.expense_payment_method_line_id = False    
            
class ProductProduct(models.Model):
    _inherit = 'product.product'

    approve_user = fields.Many2one('res.users', string='Approved By')