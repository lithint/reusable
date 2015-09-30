# -*- coding: utf-8 -*-

from openerp.osv import fields, osv

class hr_contract(osv.osv):
    _inherit = 'hr.contract'

    def get_month_salary(self, cr, uid, ids, context=None):
        def _sum_salary_rule_category(localdict, category, amount):
            if category.parent_id:
                localdict = _sum_salary_rule_category(localdict, category.parent_id, amount)
            localdict['categories'].dict[category.code] = category.code in localdict['categories'].dict and localdict['categories'].dict[category.code] + amount or amount
            return localdict

        class BrowsableObject(object):
            def __init__(self, pool, cr, uid, employee_id, dict):
                self.pool = pool
                self.cr = cr
                self.uid = uid
                self.employee_id = employee_id
                self.dict = dict

            def __getattr__(self, attr):
                return attr in self.dict and self.dict.__getitem__(attr) or 0.0

        contract_data = self.browse(cr, uid, ids[0])
        categories_dict = {}
        rules = {}
        result_dict = {}
        blacklist = []
        categories_obj = BrowsableObject(self.pool, cr, uid, contract_data.employee_id.id, categories_dict)
        rules_obj = BrowsableObject(self.pool, cr, uid, contract_data.employee_id.id, rules)

        baselocaldict = {'categories': categories_obj, 'rules': rules_obj, 'payslip': False, 'worked_days': False, 'inputs': False}

        obj_rule = self.pool.get('hr.salary.rule')

        # get the ids of the structures on the contracts and their parent id as well
        structure_ids = self.get_all_structures(cr, uid, ids, context=context)
        # get the rules of the structure and thier children
        rule_ids = self.pool.get('hr.payroll.structure').get_all_rules(cr, uid, structure_ids, context=context)
        # run the rules by sequence
        sorted_rule_ids = [id for id, sequence in sorted(rule_ids, key=lambda x:x[1])]

        for contract in self.browse(cr, uid, ids, context=context):
            employee = contract.employee_id
            localdict = dict(baselocaldict, employee=employee, contract=contract)
            for rule in obj_rule.browse(cr, uid, sorted_rule_ids, context=context):
                key = rule.code + '-' + str(contract.id)
                localdict['result'] = None
                localdict['result_qty'] = 1.0
                localdict['result_rate'] = 100
                # check if the rule can be applied
                if obj_rule.satisfy_condition(cr, uid, rule.id, localdict,
                                              context=context) and rule.id not in blacklist:
                    # compute the amount of the rule
                    amount, qty, rate = obj_rule.compute_rule(cr, uid, rule.id,
                                                              localdict,
                                                              context=context)
                    # check if there is already a rule computed with that code
                    previous_amount = rule.code in localdict and localdict[rule.code] or 0.0
                    # set/overwrite the amount computed for this rule in the localdict
                    tot_rule = amount * qty * rate / 100.0
                    localdict[rule.code] = tot_rule
                    rules[rule.code] = rule
                    # sum the amount for its salary category
                    localdict = _sum_salary_rule_category(localdict,
                                                          rule.category_id,
                                                          tot_rule - previous_amount)
                    # create/overwrite the rule in the temporary results
                    result_dict[key] = {
                        'salary_rule_id': rule.id,
                        'contract_id': contract.id,
                        'name': rule.name,
                        'code': rule.code,
                        'category_id': rule.category_id.id,
                        'sequence': rule.sequence,
                        'appears_on_payslip': rule.appears_on_payslip,
                        'condition_select': rule.condition_select,
                        'condition_python': rule.condition_python,
                        'condition_range': rule.condition_range,
                        'condition_range_min': rule.condition_range_min,
                        'condition_range_max': rule.condition_range_max,
                        'amount_select': rule.amount_select,
                        'amount_fix': rule.amount_fix,
                        'amount_python_compute': rule.amount_python_compute,
                        'amount_percentage': rule.amount_percentage,
                        'amount_percentage_base': rule.amount_percentage_base,
                        'register_id': rule.register_id.id,
                        'amount': amount,
                        'employee_id': contract.employee_id.id,
                        'quantity': qty,
                        'rate': rate,
                    }
                else:
                    # blacklist this rule and its children
                    blacklist += [id for id, seq in self.pool.get('hr.salary.rule')._recursive_search_of_rules(cr, uid, [rule], context=context)]

        result = [value for code, value in result_dict.items()]
        slry = 0.0
        for line in result:
            if str(line.get('code')) == 'NET':
                slry = line.get('amount')
        self.write(cr, uid, ids, {'month_salary': slry})
        return True


    _columns = {
        'month_salary': fields.float('Month Salary')
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
