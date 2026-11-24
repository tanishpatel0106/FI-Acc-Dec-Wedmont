"""Independent rank-statistic checks, including tied predictions."""
import numpy as np
from evaluate_age_transport import weighted_auc


def test_auc_ties_receive_half_credit():
    y=np.array([0.,1.,0.,1.])
    w=np.array([[1.,2.],[3.,1.],[2.,4.],[4.,3.]])
    assert np.allclose(weighted_auc(y,np.ones(4),w),.5)


def test_auc_matches_pairwise_definition():
    y=np.array([0.,1.,0.,1.])
    p=np.array([.1,.4,.4,.9])
    w=np.array([[1.,2.],[3.,1.],[2.,4.],[4.,3.]])
    expected=[]
    for column in w.T:
        numerator=sum(column[i]*column[j]*((p[i]>p[j])+.5*(p[i]==p[j])) for i in range(4) for j in range(4) if y[i]==1 and y[j]==0)
        expected.append(numerator/(column[y==1].sum()*column[y==0].sum()))
    assert np.allclose(weighted_auc(y,p,w),expected)
