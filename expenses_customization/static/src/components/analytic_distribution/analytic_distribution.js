/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { AnalyticDistribution, analyticDistribution } from "@analytic/components/analytic_distribution/analytic_distribution";

export class HrAnalyticDistribution extends AnalyticDistribution {

    recordProps(line) {
        const analyticAccountFields = {
            id: { type: "int" },
            display_name: { type: "char" },
            color: { type: "int" },
            plan_id: { type: "many2one" },
            root_plan_id: { type: "many2one" },
        };
        let recordFields = {};
        const values = {};
        console.log("Line in this.props.record.evalContext:", this.props.record.evalContext.active_model);
        const allowed_ids = this.props.record.evalContext?.employee_analytic_account_ids || [];

        line.analyticAccounts.map((account) => {
            const fieldName = `x_plan${account.planId}_id`;
            let domain = [["root_plan_id", "=", account.planId]];
            
            // Only add the allowed_ids filter when active_model is 'hr.expense'
            if (this.props.record.evalContext.active_model === 'hr.expense') {
                domain.push(['id', 'in', allowed_ids]);
            }
            
            recordFields[fieldName] = {
                string: account.planName,
                relation: "account.analytic.account",
                type: "many2one",
                related: {
                    fields: analyticAccountFields,
                    activeFields: analyticAccountFields,
                },
                domain: domain,
            };
            values[fieldName] =  account?.accountId || false;
        });
        recordFields['percentage'] = {
            string: _t("Percentage"),
            type: "percentage",
            cellClass: "numeric_column_width",
            ...this.decimalPrecision,
        };
        values['percentage'] = line.percentage;
        if (this.props.amount_field) {
            const { string, name, type, currency_field } = this.props.record.fields[this.props.amount_field];
            recordFields[name] = { string, name, type, currency_field, cellClass: "numeric_column_width" };
            values[name] = this.props.record.data[name] * values['percentage'];
            if (currency_field) {
                const { string, name, type, relation } = this.props.record.fields[currency_field];
                recordFields[currency_field] = { name, string, type, relation, invisible: true };
                values[currency_field] = this.props.record.data[currency_field][0];
            }
        }
        return {
            fields: recordFields,
            values: values,
            activeFields: recordFields,
            onRecordChanged: async (record, changes) => await this.lineChanged(record, changes, line),
        }
    }
}

registry.category("fields").add("analytic_distribution", {
    ...analyticDistribution,
    component: HrAnalyticDistribution,
}, { force: true });