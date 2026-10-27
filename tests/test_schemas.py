from banking_api.schemas import (
    BranchCreateRequest,
    CustomerCreate,
    CustomerUpdateRequest,
    LoanApplicationRequest,
    LoanRepaymentRequest,
    MoneyRequest,
    StaffCreateRequest,
    TransactionReversalRequest,
    TransferRequest,
)


def test_customer_display_fields_are_uppercase_but_email_is_lowercase():
    customer = CustomerCreate(
        first_name="mira",
        last_name="kapoor",
        phone="7777777777",
        age=28,
        country="iNdIa",
        state="deLHi",
        identity_number="123456789012",
        email="Mira.Kapoor@Example.com",
        address_line1="42 Green Road",
        address_city="New Delhi",
    )

    assert customer.first_name == "MIRA"
    assert customer.last_name == "KAPOOR"
    assert customer.country == "INDIA"
    assert customer.state == "DELHI"
    assert customer.address_line1 == "42 GREEN ROAD"
    assert customer.address_city == "NEW DELHI"
    assert customer.email == "mira.kapoor@example.com"


def test_all_user_entered_memos_and_reasons_are_uppercase():
    assert CustomerUpdateRequest(address_city="New Delhi").address_city == "NEW DELHI"
    assert BranchCreateRequest(ifsc="SHIV0000001", name="Main Branch").name == "MAIN BRANCH"
    assert MoneyRequest(amount="10.00", memo="cash deposit").memo == "CASH DEPOSIT"
    assert (
        TransferRequest(
            sender_account="1000000001",
            receiver_account="1000000002",
            amount="10.00",
            memo="rent payment",
        ).memo
        == "RENT PAYMENT"
    )
    assert (
        LoanApplicationRequest(
            account_number="1000000001",
            loan_type="PERSONAL",
            principal_amount="1000.00",
            interest_rate_annual=10,
            tenure_months=12,
            memo="education expense",
        ).memo
        == "EDUCATION EXPENSE"
    )
    assert LoanRepaymentRequest(amount="10.00", memo="monthly payment").memo == "MONTHLY PAYMENT"
    assert (
        TransactionReversalRequest(reason="incorrect amount").reason
        == "INCORRECT AMOUNT"
    )


def test_staff_display_name_is_uppercase_and_credentials_keep_case():
    staff = StaffCreateRequest(
        username="Staff.User",
        full_name="Mira Kapoor",
        role="TELLER",
        password="MixedCasePassword123",
    )

    assert staff.full_name == "MIRA KAPOOR"
    assert staff.username == "Staff.User"
    assert staff.password == "MixedCasePassword123"
