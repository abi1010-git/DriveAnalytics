import pytest
from app.services.rule_engine import RuleSet, evaluate_record

def rule(operator, value, match='all', enabled=True):
    return RuleSet.model_validate({'rules':[{'id':'r','name':'R','description':'D','enabled':enabled,'severity':'HIGH','match':match,'conditions':[{'field':'speed_mph','operator':operator,'value':value}]}]})

@pytest.mark.parametrize('op,value,observed,expected',[('gt',5,6,True),('gt',5,5,False),('gte',5,5,True),('lt',5,4,True),('lte',5,5,True),('eq','OK','OK',True),('neq','OK','FAILURE',True)])
def test_operators(op,value,observed,expected): assert bool(evaluate_record({'speed_mph':observed},rule(op,value))) is expected
def test_all_and_any():
    rules=RuleSet.model_validate({'rules':[{'id':'r','name':'R','description':'D','severity':'CRITICAL','match':'all','conditions':[{'field':'speed_mph','operator':'gt','value':50},{'field':'acceleration_mps2','operator':'lt','value':-4.5}]},{'id':'a','name':'A','description':'D','severity':'LOW','match':'any','conditions':[{'field':'speed_mph','operator':'gt','value':50},{'field':'sensor_status','operator':'eq','value':'FAILURE'}]}]})
    results=evaluate_record({'speed_mph':60,'acceleration_mps2':-5,'sensor_status':'OK'},rules); assert [x['rule_id'] for x in results]==['r','a']
def test_disabled_and_evidence():
    result=evaluate_record({'speed_mph':60},rule('gt',50,enabled=False)); assert result==[]
    result=evaluate_record({'speed_mph':60},rule('gt',50))[0]; assert result['evidence'][0]['observed']==60 and result['evidence'][0]['threshold']==50
def test_invalid_rules():
    with pytest.raises(ValueError): RuleSet.model_validate({'rules':[{'id':'r','name':'R','description':'D','severity':'HIGH','conditions':[{'field':'bad','operator':'gt','value':1}]}]})
    with pytest.raises(ValueError): RuleSet.model_validate({'rules':[{'id':'r','name':'R','description':'D','severity':'HIGH','conditions':[{'field':'speed_mph','operator':'eval','value':1}]}]})
    with pytest.raises(ValueError): RuleSet.model_validate({'rules':[{'id':'r','name':'R','description':'D','severity':'HIGH','conditions':[{'field':'speed_mph','operator':'gt','value':1}]},{'id':'r','name':'R2','description':'D','severity':'LOW','conditions':[{'field':'speed_mph','operator':'gt','value':2}]}]})
