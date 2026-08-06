package in.novopay.accounting.loan.grouploan.disbursement.service;

import in.novopay.infra.platform.exception.NovopayFatalException;
import in.novopay.infra.platform.navigation.ExecutionContext;
import org.json.simple.JSONArray;
import org.json.simple.JSONObject;

import java.lang.reflect.Proxy;
import java.util.HashMap;
import java.util.Map;

public class ClbParentRepAcctFallbackRunner {

    private static int failures = 0;

    public static void main(String[] args) {
        System.out.println("Verify mode: REAL invocation of ChildLoanBookingEventsQueueDataPopulator.ensureMemberHasUsableRepAcct");

        memberOwnRepAcctKept();
        parentRepAcctCopiedWhenMemberMissing();
        blankMemberStubReplacedByParent();
        noParentRepAcctStillFailsClosed();
        cashRepaymentSkipsCopy();
        eachMemberGetsIndependentCopy();
        originalRequestUsedWhenSharedCopyIsStub();

        if (failures > 0) {
            System.out.println("FAIL: clb parent REP_ACCT fallback — " + failures + " assert(s) failed");
            System.exit(1);
        }
        System.out.println("PASS: clb parent REP_ACCT fallback");
    }

    private static void memberOwnRepAcctKept() {
        JSONArray member = array(repAcct("M-REP"));
        ExecutionContext ec = context("DIRDR", array(repAcct("P-REP")));

        run(ec, member);

        check("member own REP_ACCT kept", 1, countRepAcct(member));
        check("member own account_number untouched", "M-REP", firstRepAcctNumber(member));
    }

    private static void parentRepAcctCopiedWhenMemberMissing() {
        JSONArray member = array(dsbrAcct("M-DSBR"));
        ExecutionContext ec = context("DIRDR", array(dsbrAcct("P-DSBR"), repAcct("P-REP")));

        run(ec, member);

        check("parent REP_ACCT copied exactly once", 1, countRepAcct(member));
        check("copied account_number is parent CASA", "P-REP", firstRepAcctNumber(member));
        check("member DSBR_ACCT preserved", 2, member.size());
    }

    private static void blankMemberStubReplacedByParent() {
        JSONArray member = array(repAcct(""));
        ExecutionContext ec = context("ACH", array(repAcct("P-REP")));

        run(ec, member);

        check("blank stub dropped, parent copied", 1, countRepAcct(member));
        check("blank stub replaced by parent CASA", "P-REP", firstRepAcctNumber(member));
    }

    private static void noParentRepAcctStillFailsClosed() {
        JSONArray member = array(dsbrAcct("M-DSBR"));
        ExecutionContext ec = context("DIRDR", array(dsbrAcct("P-DSBR")));

        String code = runExpectingFailure(ec, member);

        check("no member and no parent REP_ACCT throws 130142", "130142", code);
    }

    private static void cashRepaymentSkipsCopy() {
        JSONArray member = array(dsbrAcct("M-DSBR"));
        ExecutionContext ec = context("CASH", array(repAcct("P-REP")));

        run(ec, member);

        check("CASH does not copy parent REP_ACCT", 0, countRepAcct(member));
    }

    private static void eachMemberGetsIndependentCopy() {
        JSONArray memberOne = array(dsbrAcct("M1-DSBR"));
        JSONArray memberTwo = array(dsbrAcct("M2-DSBR"));
        JSONArray parent = array(repAcct("P-REP"));
        ExecutionContext ec = context("DIRDR", parent);

        run(ec, memberOne);
        run(ec, memberTwo);

        JSONObject copyOne = firstRepAcct(memberOne);
        JSONObject copyTwo = firstRepAcct(memberTwo);
        check("both members carry parent CASA", "P-REP", String.valueOf(copyTwo.get("account_number")));
        check("copies are distinct objects", true, copyOne != copyTwo);

        copyOne.put("account_number", "MUTATED");
        check("mutating one copy leaves parent array intact", "P-REP", firstRepAcctNumber(parent));
        check("mutating one copy leaves sibling intact", "P-REP", firstRepAcctNumber(memberTwo));
    }

    private static void originalRequestUsedWhenSharedCopyIsStub() {
        JSONArray member = array(dsbrAcct("M-DSBR"));
        JSONArray sharedStub = array(repAcct(""));
        JSONArray originalRequest = array(repAcct("P-REP"));
        ExecutionContext ec = context("DIRDR", sharedStub, originalRequest);

        run(ec, member);

        check("stub shared copy falls through to original request", 1, countRepAcct(member));
        check("original request CASA copied", "P-REP", firstRepAcctNumber(member));
    }

    private static void run(ExecutionContext ec, JSONArray member) {
        try {
            ChildLoanBookingEventsQueueDataPopulator.ensureMemberHasUsableRepAcct(ec, member);
        } catch (NovopayFatalException e) {
            failures++;
            System.out.println("  FAIL unexpected " + e.getErrorCode());
        }
    }

    private static String runExpectingFailure(ExecutionContext ec, JSONArray member) {
        try {
            ChildLoanBookingEventsQueueDataPopulator.ensureMemberHasUsableRepAcct(ec, member);
            return "NO_EXCEPTION";
        } catch (NovopayFatalException e) {
            return e.getErrorCode();
        }
    }

    @SuppressWarnings("unchecked")
    private static JSONArray array(JSONObject... entries) {
        JSONArray jsonArray = new JSONArray();
        for (JSONObject entry : entries) {
            jsonArray.add(entry);
        }
        return jsonArray;
    }

    @SuppressWarnings("unchecked")
    private static JSONObject repAcct(String accountNumber) {
        return accountDetail("REP_ACCT", accountNumber);
    }

    @SuppressWarnings("unchecked")
    private static JSONObject dsbrAcct(String accountNumber) {
        return accountDetail("DSBR_ACCT", accountNumber);
    }

    @SuppressWarnings("unchecked")
    private static JSONObject accountDetail(String code, String accountNumber) {
        JSONObject purpose = new JSONObject();
        purpose.put("code", code);
        JSONArray purposeArray = new JSONArray();
        purposeArray.add(purpose);
        JSONObject detail = new JSONObject();
        detail.put("purpose", purposeArray);
        detail.put("account_number", accountNumber);
        return detail;
    }

    private static int countRepAcct(JSONArray details) {
        int count = 0;
        for (Object obj : details) {
            if (isRepAcct(obj)) {
                count++;
            }
        }
        return count;
    }

    private static JSONObject firstRepAcct(JSONArray details) {
        for (Object obj : details) {
            if (isRepAcct(obj)) {
                return (JSONObject) obj;
            }
        }
        return null;
    }

    private static String firstRepAcctNumber(JSONArray details) {
        JSONObject detail = firstRepAcct(details);
        return detail == null ? null : String.valueOf(detail.get("account_number"));
    }

    private static boolean isRepAcct(Object obj) {
        if (!(obj instanceof JSONObject)) {
            return false;
        }
        Object purposeObj = ((JSONObject) obj).get("purpose");
        if (!(purposeObj instanceof JSONArray)) {
            return false;
        }
        for (Object purposeEntry : (JSONArray) purposeObj) {
            Object code = ((JSONObject) purposeEntry).get("code");
            if (code != null && "REP_ACCT".equalsIgnoreCase(code.toString())) {
                return true;
            }
        }
        return false;
    }

    private static ExecutionContext context(String repaymentMode, JSONArray parentDetails) {
        return context(repaymentMode, parentDetails, parentDetails);
    }

    private static ExecutionContext context(String repaymentMode, JSONArray parentDetails, JSONArray originalDetails) {
        Map<String, Object> state = new HashMap<>();
        Map<String, Object> original = new HashMap<>();
        state.put("repayment_mode", repaymentMode);
        state.put("disbursement_repayment_account_details", parentDetails);
        original.put("disbursement_repayment_account_details", originalDetails);
        return (ExecutionContext) Proxy.newProxyInstance(
                ClbParentRepAcctFallbackRunner.class.getClassLoader(),
                new Class<?>[]{ExecutionContext.class},
                (proxy, method, methodArgs) -> switch (method.getName()) {
                    case "get" -> state.get((String) methodArgs[0]);
                    case "put", "putLocal" -> {
                        state.put((String) methodArgs[0], methodArgs[1]);
                        yield null;
                    }
                    case "getValue" -> ((Class<?>) methodArgs[1]).cast(state.get((String) methodArgs[0]));
                    case "getOriginalRequest" -> original;
                    default -> null;
                });
    }

    private static void check(String what, Object expected, Object actual) {
        if (expected.equals(actual)) {
            System.out.println("  PASS " + what);
            return;
        }
        failures++;
        System.out.println("  FAIL " + what + " — expected " + expected + ", got " + actual);
    }
}
