# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo import api, fields, Command, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_date
from odoo.tools import float_round
from datetime import datetime, date, timedelta
from num2words import num2words
from odoo.tools.misc import clean_context
import logging
_logger = logging.getLogger(__name__)

class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'
    
    @api.model
    def create(self, vals):
        record = super(HrExpenseSheet, self).create(vals)
        if record.employee_id and record.sudo().employee_id.expense_payment_method_line_id:
            record.payment_method_line_id = record.sudo().employee_id.expense_payment_method_line_id.id
        return record

    @api.onchange('employee_id')
    def onchange_expense_employee_id(self):
        if self.sudo().employee_id and self.sudo().employee_id.expense_payment_method_line_id:
            self.payment_method_line_id = self.sudo().employee_id.expense_payment_method_line_id.id
        else:
            self.payment_method_line_id = False
    
    def _prepare_bills_vals(self):
        res = super(HrExpenseSheet, self)._prepare_bills_vals()
        res['attachment_ids'] = [
                Command.create(attachment.copy_data({'res_model': 'account.move', 'res_id': False, 'raw': attachment.raw})[0])
                for attachment in self.expense_line_ids.attachment_ids
            ]
        return res

    
class HrExpense(models.Model):
    _inherit = 'hr.expense'

    location_numbers_id = fields.Many2one('location.numbers', string='Location Numbers')
    vendor_name = fields.Char(string='Vendor')
    vat = fields.Char(string='VAT')
    invoice_number = fields.Char(string='Invoice Number')
    analytic_location_numbers_ids = fields.Many2many('location.numbers', string='Location Numbers',compute='_compute_analytic_location_numbers_ids')
    location_numbers_required = fields.Boolean(compute='_compute_location_numbers_required', store=False)
    employee_analytic_account_ids = fields.Many2many('account.analytic.account', related='employee_id.analytic_account_ids', string='Employee Analytic Accounts', readonly=True)
    payment_mode = fields.Selection(default='company_account')
    state = fields.Selection(selection_add=[
            ('draft', 'To Report'),
            ('category_approve', 'Category Approve'),   
            ('project_approve', 'Project Approve'), 
            ('reported', 'To Submit'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('done', 'Done'),
            ('gm_approve', 'GM Approve'),
            ('refused', 'Refused')
        ], string="Status", compute='_compute_state', store=True, readonly=True, index=True, copy=False, default='draft',
    )
    @api.constrains('vat')
    def _check_vat_length(self):
        for record in self:
            if record.vat and not (record.vat.isdigit() and len(record.vat) == 15):
                raise ValidationError(_('VAT must be exactly 15 digits.'))

    @api.depends('sheet_id', 'sheet_id.account_move_ids', 'sheet_id.state')
    def _compute_state(self):
        for expense in self:
            if not expense.sheet_id:
                expense.state = 'draft'
            elif expense.sheet_id.state == 'draft':
                expense.state = 'reported'
            elif expense.sheet_id.state == 'cancel':
                expense.state = 'refused'
            elif expense.sheet_id.state in {'approve', 'post'}:
                expense.state = 'approved'
            elif not expense.sheet_id.account_move_ids:
                expense.state = 'submitted'
            else:
                expense.state = 'done'
    # Computed fields for button visibility
    show_category_approve_button = fields.Boolean(compute='_compute_show_approval_buttons')
    show_project_approve_button = fields.Boolean(compute='_compute_show_approval_buttons')
    
    # Helper fields for record rules
    analytic_approve_user_ids = fields.Many2many('res.users', compute='_compute_analytic_approve_user_ids', store=True, string='Analytic Approve Users')

    @api.depends('analytic_distribution')
    def _compute_analytic_approve_user_ids(self):
        for record in self:
            approve_users = self.env['res.users']
            if record.analytic_distribution:
                try:
                    analytic_ids = []
                    for key in record.analytic_distribution.keys():
                        # Handle both single IDs and comma-separated IDs
                        if ',' in str(key):
                            # Split comma-separated values and convert to integers
                            ids = [int(id_str.strip()) for id_str in str(key).split(',') if id_str.strip().isdigit()]
                            analytic_ids.extend(ids)
                        else:
                            # Single ID
                            if str(key).isdigit():
                                analytic_ids.append(int(key))
                    
                    if analytic_ids:
                        analytic_accounts = self.env['account.analytic.account'].browse(analytic_ids)
                        approve_users = analytic_accounts.mapped('approve_user').filtered(lambda u: u)
                except (ValueError, TypeError) as e:
                    # Log the error and continue with empty approve_users
                    _logger.warning("Error parsing analytic_distribution for expense %s: %s", record.id, e)
            record.analytic_approve_user_ids = approve_users

    @api.depends('analytic_distribution')
    def _compute_location_numbers_required(self):
        for record in self:
            record.location_numbers_required = False
            if record.analytic_distribution:
                analytic_account_ids = []
                for acc_id_str in record.analytic_distribution.keys():
                    try:
                        if ',' in str(acc_id_str):
                            ids = [int(x.strip()) for x in str(acc_id_str).split(',') if x.strip().isdigit()]
                            analytic_account_ids.extend(ids)
                        else:
                            analytic_account_ids.append(int(acc_id_str))
                    except ValueError:
                        continue
                
                if analytic_account_ids:
                    analytic_accounts = self.env['account.analytic.account'].browse(analytic_account_ids)
                    for account in analytic_accounts:
                        if hasattr(account, 'location_numbers_ids') and account.location_numbers_ids:
                            record.location_numbers_required = True
                            break

    @api.depends('analytic_distribution')
    def _compute_analytic_location_numbers_ids(self):
        for record in self:
            location_numbers = self.env['location.numbers']
            if record.analytic_distribution:
                analytic_account_ids = []
                for acc_id_str in record.analytic_distribution.keys():
                    try:
                        if ',' in str(acc_id_str):
                            ids = [int(x.strip()) for x in str(acc_id_str).split(',') if x.strip().isdigit()]
                            analytic_account_ids.extend(ids)
                        else:
                            analytic_account_ids.append(int(acc_id_str))
                    except ValueError:
                        continue
                
                if analytic_account_ids:
                    analytic_accounts = self.env['account.analytic.account'].browse(analytic_account_ids)
                    for account in analytic_accounts:
                        if hasattr(account, 'location_numbers_ids') and account.location_numbers_ids:
                            location_numbers |= account.location_numbers_ids
            record.analytic_location_numbers_ids = location_numbers

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            self.analytic_distribution = {}
        else:
            self.analytic_distribution = {}


    @api.onchange('analytic_distribution')
    def _onchange_analytic_distribution(self):
        if self.location_numbers_id and self.analytic_location_numbers_ids:
            if self.location_numbers_id not in self.analytic_location_numbers_ids:
                self.location_numbers_id = False

    @api.depends('state', 'product_id', 'analytic_distribution')
    def _compute_show_approval_buttons(self):
        current_user = self.env.user
        
        for record in self:
            record.show_category_approve_button = False
            record.show_project_approve_button = False
            
            if record.state == 'category_approve' and record.product_id and record.product_id.approve_user:
                record.show_category_approve_button = (current_user.id == record.product_id.approve_user.id)
            
            if record.state == 'project_approve' and record.analytic_distribution:
                analytic_account_ids = []
                for acc_id_str in record.analytic_distribution.keys():
                    try:
                        if ',' in str(acc_id_str):
                            ids = [int(x.strip()) for x in str(acc_id_str).split(',') if x.strip().isdigit()]
                            analytic_account_ids.extend(ids)
                        else:
                            analytic_account_ids.append(int(acc_id_str))
                    except ValueError:
                        continue
                
                if analytic_account_ids:
                    analytic_accounts = self.env['account.analytic.account'].browse(analytic_account_ids)
                    for account in analytic_accounts:
                        if account.approve_user and account.approve_user.id == current_user.id:
                            record.show_project_approve_button = True
                            break
            

    def action_category_approve(self):
        if self.show_category_approve_button:
            self.write({'state': 'project_approve'})
        else:
            raise ValidationError(_('You are not authorized to approve this expense at category level.'))
        
    def _get_default_expense_sheet_values(self):
        # If there is an expense with total_amount == 0, it means that expense has not been processed by OCR yet
        expenses_with_amount = self.filtered(lambda expense: not (
            expense.currency_id.is_zero(expense.total_amount_currency)
            or expense.company_currency_id.is_zero(expense.total_amount)
            or (expense.product_id and not float_round(expense.quantity, precision_rounding=expense.product_uom_id.rounding))
        ))

        if any(expense.sheet_id for expense in expenses_with_amount):
            raise UserError(_("You cannot report twice the same line!"))
        if not expenses_with_amount:
            raise UserError(_("You cannot report the expenses without amount!"))
        if len(expenses_with_amount.mapped('employee_id')) != 1:
            raise UserError(_("You cannot report expenses for different employees in the same report."))
        if any(not expense.product_id for expense in expenses_with_amount):
            raise UserError(_("You can not create report without category."))
        if len(self.company_id) != 1:
            raise UserError(_("You cannot report expenses for different companies in the same report."))

        # Check if two reports should be created
        own_expenses = expenses_with_amount.filtered(lambda x: x.payment_mode == 'own_account')
        company_expenses = expenses_with_amount - own_expenses
        create_two_reports = own_expenses and company_expenses

        sheets = (own_expenses, company_expenses) if create_two_reports else (expenses_with_amount,)
        values = []

        # We use a fallback name only when several expense sheets are created,
        # else we use the form view required name to force the user to set a name
        for todo in sheets:
            paid_by = 'company' if todo[0].payment_mode == 'company_account' else 'employee'
            sheet_name = _("New Expense Report, paid by %(paid_by)s", paid_by=paid_by) if len(sheets) > 1 else False
            if len(todo) == 1:
                sheet_name = todo.name
            else:
                dates = todo.mapped('date')
                if False not in dates:  # If at least one date isn't set, we don't set a default name
                    min_date = format_date(self.env, min(dates))
                    max_date = format_date(self.env, max(dates))
                    if min_date == max_date:
                        sheet_name = min_date
                    else:
                        sheet_name = _("%(date_from)s - %(date_to)s", date_from=min_date, date_to=max_date)

            values.append({
                'company_id': self.company_id.id,
                'employee_id': self[0].employee_id.id,
                'name': sheet_name,
                'expense_line_ids': [Command.set(todo.ids)],
                'state': 'draft',
            })
        return values
    
    def action_project_approve(self):
        if self.filtered(lambda expense: not expense.is_editable):
            raise UserError(_('You are not authorized to edit this expense.'))
        sheets = self.env['hr.expense.sheet'].create(self._get_default_expense_sheet_values())
        
        sheets._do_submit()
        sheets.action_approve_expense_sheets()
        self.write({'state': 'approved'})
        return {
            'name': _('New Expense Reports'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.expense.sheet',
            'context': self.env.context,
            'views': [[False, "list"], [False, "form"]] if len(sheets) > 1 else [[False, "form"]],
            'domain': [('id', 'in', sheets.ids)],
            'res_id': sheets.id if len(sheets) == 1 else False,
        }
        
    def action_gm_approve(self):
        self.write({'state': 'gm_approve'})


   
    def action_confirm_approve(self):
        self.write({'state': 'category_approve'})
        self._compute_show_approval_buttons()

    @api.constrains('location_numbers_id', 'analytic_distribution')
    def _check_location_numbers_required(self):
        for record in self:
            if record.location_numbers_required and not record.location_numbers_id:
                raise ValidationError(_('Location Numbers is required when analytic accounts have location numbers assigned.'))

    def _prepare_payments_vals(self):
        res = super(HrExpense, self)._prepare_payments_vals()
        res['attachment_ids'] = [
                Command.create(attachment.copy_data({'res_model': 'account.move', 'res_id': False, 'raw': attachment.raw})[0])
                for attachment in self.attachment_ids
            ]
        return res
