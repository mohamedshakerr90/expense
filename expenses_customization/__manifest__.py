# -*- coding: utf-8 -*-
{
    'name': "Expenses Customization",

    'summary': """Expenses Customization""",

    'description': """Expenses Customization""",

    'author': "Omar Adel",
    'website': "http://www.omaradel.com",
    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['base', 'hr_expense', 'account', 'analytic', 'hr', 'account_accountant'],

    'data': [
        'security/ir.model.access.csv',
        'security/hr_expense_record_rules.xml',
        'views/location_number.xml',
        'views/views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'expenses_customization/static/src/components/**/*',
        ]
    },
    'installable': True,
    'application': True,
}
