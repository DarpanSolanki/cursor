import in.novopay.accounting.account.loans.constant.LoanAccountConstants;
import in.novopay.accounting.account.loans.entity.LoanAccountEntity;
import in.novopay.accounting.account.loans.repository.LoanAccountDAOService;
import in.novopay.accounting.loan.prepayment.processor.UpdateLoanStatusForSHGProcessor;
import in.novopay.infra.platform.navigation.DefaultExecutionContext;
import in.novopay.infra.platform.navigation.ExecutionContext;

import java.lang.reflect.Field;
import java.util.ArrayList;
import java.util.List;

public class ShgSweepProbe {

    static final Long PARENT_ID = 384460L;
    static List<LoanAccountEntity> saved = new ArrayList<>();

    static class StubDao extends LoanAccountDAOService {
        private final List<LoanAccountEntity> children;
        StubDao(List<LoanAccountEntity> children) { this.children = children; }
        @Override public List<LoanAccountEntity> findAllByParentAccountId(Long id) { return children; }
        @Override public List<LoanAccountEntity> findAllByParentAccountNonClosed(Long id) { return children; }
        @Override public List<LoanAccountEntity> saveAll(List<LoanAccountEntity> e) { saved = new ArrayList<>(e); return e; }
    }

    static LoanAccountEntity loan(Long id, LoanAccountEntity.LoanStatus st) {
        LoanAccountEntity e = new LoanAccountEntity();
        e.setId(id);
        e.setLoanStatus(st);
        return e;
    }

    static void inject(Object target, String field, Object value) throws Exception {
        Field f = target.getClass().getDeclaredField(field);
        f.setAccessible(true);
        f.set(target, value);
    }

    static boolean scenario(String label, String loanStatus, String stage,
                            List<LoanAccountEntity> children, LoanAccountEntity victim,
                            LoanAccountEntity.LoanStatus expectVictim) throws Exception {
        saved = new ArrayList<>();
        UpdateLoanStatusForSHGProcessor p = new UpdateLoanStatusForSHGProcessor();
        inject(p, "loanAccountDAOService", new StubDao(children));
        LoanAccountEntity parent = loan(PARENT_ID, LoanAccountEntity.LoanStatus.ACTIVE);
        parent.setHasChildAccounts(true);
        ExecutionContext ctx = new DefaultExecutionContext();
        ctx.put("loan_account_entity", parent);
        ctx.put(LoanAccountConstants.LOAN_STATUS, loanStatus);
        ctx.put("stage", stage);
        p.execute(ctx);
        boolean ok = victim.getLoanStatus() == expectVictim;
        System.out.println((ok ? "PASS  " : "FAIL  ") + label
                + " | victim=" + victim.getLoanStatus() + " expected=" + expectVictim
                + " | savedIds=" + saved.stream().map(LoanAccountEntity::getId).toList());
        return ok;
    }

    public static void main(String[] args) throws Exception {
        boolean all = true;

        LoanAccountEntity sib1 = loan(1L, LoanAccountEntity.LoanStatus.ACTIVE);
        LoanAccountEntity cancelled1 = loan(2L, LoanAccountEntity.LoanStatus.DISB_CNCL);
        LoanAccountEntity closed1 = loan(3L, LoanAccountEntity.LoanStatus.CLOSED);
        all &= scenario("INITIATE parent sweep must not freeze a cancelled child",
                "FORECLOSURE_FREEZE", "INITIATE", List.of(sib1, cancelled1, closed1),
                cancelled1, LoanAccountEntity.LoanStatus.DISB_CNCL);
        all &= (sib1.getLoanStatus() == LoanAccountEntity.LoanStatus.FORECLOSURE_FREEZE);
        System.out.println("      sibling correctly frozen = " + sib1.getLoanStatus());
        System.out.println("      closed child untouched   = " + closed1.getLoanStatus());

        LoanAccountEntity sib2 = loan(1L, LoanAccountEntity.LoanStatus.FORECLOSURE_FREEZE);
        LoanAccountEntity cancelled2 = loan(2L, LoanAccountEntity.LoanStatus.DISB_CNCL);
        all &= scenario("FINAL parent sweep must not reactivate a cancelled child",
                "CLOSED", "FINAL", List.of(sib2, cancelled2),
                cancelled2, LoanAccountEntity.LoanStatus.DISB_CNCL);
        all &= (sib2.getLoanStatus() == LoanAccountEntity.LoanStatus.ACTIVE);
        System.out.println("      sibling correctly reactivated = " + sib2.getLoanStatus());

        System.out.println(all ? "=== GREEN" : "=== RED");
        System.exit(all ? 0 : 1);
    }
}
