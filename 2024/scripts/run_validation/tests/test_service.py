import time
import multiprocessing
import random

import pytest

from passage_validator import PassageValidator
from main import validate, GRPC_DEFAULT_TIMEOUT, EXPECTED_RUN_TURN_COUNT


def test_service_startup(servicer_params_test):
    """
    Test that the PassageValidator service loads a sample database correctly.
    """
    pv = PassageValidator(*servicer_params_test)
    assert pv.db.rowcount() == servicer_params_test[1]


def test_service_startup_invalid_rows(servicer_params_test):
    """
    Test that the service fails to start if the database has an unexpected row count.
    """
    with pytest.raises(SystemExit) as pytest_exc:
        # this should cause the service to exit because the sample database has
        # 10,000 rows instead of 12,345
        _ = PassageValidator(servicer_params_test[0], 12345)

    assert pytest_exc.type is SystemExit
    assert pytest_exc.value.code == 255


def validate_wrapper(run_file: str, file_root: str, max_warnings: int, skip_validation: bool, start_delay: float):
    time.sleep(start_delay)
    turns_validated, service_errors, warning_count = validate(
        run_file, file_root, max_warnings, skip_validation, timeout=GRPC_DEFAULT_TIMEOUT
    )
    return (turns_validated, service_errors, warning_count)


@pytest.mark.skip("Currently broken")
def test_service_multiple_clients(default_validate_args, grpc_server_full):
    """
    Test that the service handles multiple clients.
    """
    num_clients = 25
    args = default_validate_args

    validation_args = [
        (args.path_to_run_file, args.fileroot, 10_000, args.skip_passage_validation, random.random())
        for x in range(num_clients)
    ]

    with multiprocessing.Pool(processes=num_clients) as pool:
        results = pool.starmap(validate_wrapper, validation_args)

    for i in range(num_clients):
        assert results[i] == (EXPECTED_RUN_TURN_COUNT, 0, 1992)
