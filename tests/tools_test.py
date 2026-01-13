# test_mcp_tools.py
"""
Test suite for MCP Tools - DevOps Agent
Tests all 3 tools: create_ticket, get_ticket, append_note

Run with: python test_mcp_tools.py
"""
import requests
import json
import time
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"
CLIENT_ID = "vip-test-tools"  # Use VIP to avoid rate limiting during tests


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print formatted header"""
    print(f"\n{Colors.CYAN}{Colors.BOLD}{'=' * 70}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{text}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'=' * 70}{Colors.RESET}\n")


def print_test(test_name: str):
    """Print test name"""
    print(f"{Colors.BLUE}[TEST] {test_name}{Colors.RESET}")


def print_success(message: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")


def print_error(message: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")


def print_info(message: str):
    """Print info message"""
    print(f"{Colors.YELLOW}→ {message}{Colors.RESET}")


def print_result(data: Dict[str, Any]):
    """Print formatted JSON result"""
    print(f"{Colors.MAGENTA}{json.dumps(data, indent=2)}{Colors.RESET}")


def make_request(message: str) -> Dict[str, Any]:
    """
    Make request to agent API

    Args:
        message: Query message

    Returns:
        Response JSON
    """
    url = f"{BASE_URL}/agent/query"
    payload = {
        "message": message,
        "top_k": 2
    }
    headers = {
        "Content-Type": "application/json",
        "X-Client-ID": CLIENT_ID
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            print_error(f"Rate limited! Using VIP tier should prevent this.")
            print_info("Waiting 5 seconds...")
            time.sleep(5)
            return make_request(message)  # Retry
        else:
            print_error(f"HTTP {response.status_code}: {response.text}")
            return {"error": f"HTTP {response.status_code}"}
    except Exception as e:
        print_error(f"Request failed: {str(e)}")
        return {"error": str(e)}


def test_tool_1_create_ticket():
    """
    Test Tool 1: create_ticket
    Creates incident tickets with different priorities
    """
    print_header("TEST TOOL 1: create_ticket")

    test_cases = [
        {
            "name": "Create Critical Ticket",
            "message": "Create a critical ticket for database server down",
            "expected_priority": "critical",
            "expected_in_summary": "database"
        },
        {
            "name": "Create High Priority Ticket",
            "message": "Create a high priority ticket for API latency issues",
            "expected_priority": "high",
            "expected_in_summary": "API"
        },
        {
            "name": "Create Medium Priority Ticket",
            "message": "Create a ticket for slow report generation",
            "expected_priority": "medium",
            "expected_in_summary": "report"
        },
    ]

    results = []

    for i, test_case in enumerate(test_cases, 1):
        print_test(f"{i}. {test_case['name']}")
        print_info(f"Message: {test_case['message']}")

        response = make_request(test_case['message'])

        if "error" in response:
            print_error("Request failed")
            results.append(False)
            continue

        # Check tool was called
        tool_calls = response.get("tool_calls", [])

        if not tool_calls:
            print_error("No tool calls found in response")
            results.append(False)
            continue

        # Find create_ticket call
        ticket_call = None
        for call in tool_calls:
            if call.get("tool") == "create_ticket":
                ticket_call = call
                break

        if not ticket_call:
            print_error("create_ticket not called")
            print_info(f"Tools called: {[c.get('tool') for c in tool_calls]}")
            results.append(False)
            continue

        # Verify output
        output = ticket_call.get("output", {})
        ticket_id = output.get("ticket_id")
        priority = output.get("priority")
        summary = output.get("summary", "")

        print_success(f"Ticket created with ID: {ticket_id}")
        print_success(f"Priority: {priority}")
        print_success(f"Summary: {summary}")

        # Validate
        passed = True

        if ticket_id is None:
            print_error("No ticket_id in response")
            passed = False

        if priority != test_case["expected_priority"]:
            print_error(f"Expected priority '{test_case['expected_priority']}', got '{priority}'")
            passed = False

        if test_case["expected_in_summary"].lower() not in summary.lower():
            print_error(f"Expected '{test_case['expected_in_summary']}' in summary")
            passed = False

        if passed:
            print_success("Test PASSED")
        else:
            print_error("Test FAILED")

        results.append(passed)
        print()

    # Summary
    passed_count = sum(results)
    total_count = len(results)

    print(f"\n{Colors.BOLD}Tool 1 Summary: {passed_count}/{total_count} tests passed{Colors.RESET}")

    return results


def test_tool_2_get_ticket():
    """
    Test Tool 2: get_ticket
    Retrieves ticket details by ID
    """
    print_header("TEST TOOL 2: get_ticket")

    # First, create a ticket to retrieve
    print_info("Setting up: Creating a test ticket...")
    create_response = make_request("Create a test ticket for SSL certificate expiring")

    # Extract ticket ID from tool calls
    ticket_id = None
    for call in create_response.get("tool_calls", []):
        if call.get("tool") == "create_ticket":
            ticket_id = call.get("output", {}).get("ticket_id")
            break

    if not ticket_id:
        print_error("Failed to create test ticket")
        return [False]

    print_success(f"Test ticket created with ID: {ticket_id}")
    print()

    # Now test get_ticket
    test_cases = [
        {
            "name": "Get Existing Ticket",
            "message": f"Get ticket {ticket_id}",
            "ticket_id": ticket_id,
            "should_find": True
        },
        {
            "name": "Get Non-existent Ticket",
            "message": "Get ticket 99999",
            "ticket_id": 99999,
            "should_find": False
        }
    ]

    results = []

    for i, test_case in enumerate(test_cases, 1):
        print_test(f"{i}. {test_case['name']}")
        print_info(f"Message: {test_case['message']}")

        response = make_request(test_case['message'])

        if "error" in response:
            print_error("Request failed")
            results.append(False)
            continue

        # Check tool was called
        tool_calls = response.get("tool_calls", [])

        # Find get_ticket call
        get_call = None
        for call in tool_calls:
            if call.get("tool") == "get_ticket":
                get_call = call
                break

        if not get_call:
            print_error("get_ticket not called")
            results.append(False)
            continue

        # Verify output
        output = get_call.get("output", {})
        found = output.get("found", False)

        if test_case["should_find"]:
            if found:
                ticket_data = output.get("ticket", {})
                print_success(f"Ticket found: ID={ticket_data.get('id')}")
                print_success(f"  Summary: {ticket_data.get('summary')}")
                print_success(f"  Priority: {ticket_data.get('priority')}")
                print_success(f"  Status: {ticket_data.get('status')}")
                results.append(True)
                print_success("Test PASSED")
            else:
                print_error("Ticket should be found but wasn't")
                results.append(False)
                print_error("Test FAILED")
        else:
            if not found:
                print_success("Ticket correctly not found")
                results.append(True)
                print_success("Test PASSED")
            else:
                print_error("Ticket should not be found but was")
                results.append(False)
                print_error("Test FAILED")

        print()

    # Summary
    passed_count = sum(results)
    total_count = len(results)

    print(f"\n{Colors.BOLD}Tool 2 Summary: {passed_count}/{total_count} tests passed{Colors.RESET}")

    return results


def test_tool_3_append_note():
    """
    Test Tool 3: append_note
    Appends notes to entities
    """
    print_header("TEST TOOL 3: append_note")

    test_cases = [
        {
            "name": "Append Note to Deployment",
            "message": "Append note to deploy-2024-01: Deployment completed successfully at 3 PM",
            "expected_entity": "deploy-2024-01",
            "expected_in_note": "successfully"
        },
        {
            "name": "Append Note to Server",
            "message": "Append note to web-prod-01: Memory usage increased to 85% after deployment",
            "expected_entity": "web-prod-01",
            "expected_in_note": "Memory"
        },
        {
            "name": "Append Note to Ticket",
            "message": "Append note to ticket-123: Customer confirmed issue is resolved",
            "expected_entity": "ticket-123",
            "expected_in_note": "resolved"
        }
    ]

    results = []

    for i, test_case in enumerate(test_cases, 1):
        print_test(f"{i}. {test_case['name']}")
        print_info(f"Message: {test_case['message']}")

        response = make_request(test_case['message'])

        if "error" in response:
            print_error("Request failed")
            results.append(False)
            continue

        # Check tool was called
        tool_calls = response.get("tool_calls", [])

        # Find append_note call
        note_call = None
        for call in tool_calls:
            if call.get("tool") == "append_note":
                note_call = call
                break

        if not note_call:
            print_error("append_note not called")
            results.append(False)
            continue

        # Verify input and output
        input_data = note_call.get("input", {})
        output = note_call.get("output", {})

        entity_id = input_data.get("entity_id")
        note_text = input_data.get("note")
        ok = output.get("ok", False)
        note_id = output.get("note_id")

        print_success(f"Note appended: ID={note_id}")
        print_success(f"  Entity: {entity_id}")
        print_success(f"  Note: {note_text[:50]}...")

        # Validate
        passed = True

        if not ok:
            print_error("Operation not marked as OK")
            passed = False

        if note_id is None:
            print_error("No note_id in response")
            passed = False

        if test_case["expected_entity"] not in entity_id:
            print_error(f"Expected entity '{test_case['expected_entity']}', got '{entity_id}'")
            passed = False

        if test_case["expected_in_note"].lower() not in note_text.lower():
            print_error(f"Expected '{test_case['expected_in_note']}' in note")
            passed = False

        if passed:
            print_success("Test PASSED")
        else:
            print_error("Test FAILED")

        results.append(passed)
        print()

    # Summary
    passed_count = sum(results)
    total_count = len(results)

    print(f"\n{Colors.BOLD}Tool 3 Summary: {passed_count}/{total_count} tests passed{Colors.RESET}")

    return results


def test_combined_workflow():
    """
    Test combining multiple tools in one workflow
    """
    print_header("TEST COMBINED WORKFLOW")

    print_test("Full Incident Management Workflow")
    print_info("Step 1: Create incident ticket")
    print_info("Step 2: Get ticket details")
    print_info("Step 3: Append resolution note")
    print()

    # Step 1: Create ticket
    print(f"{Colors.YELLOW}→ Step 1: Creating incident...{Colors.RESET}")
    create_msg = "Create a high priority incident for application server not responding"
    create_response = make_request(create_msg)

    ticket_id = None
    for call in create_response.get("tool_calls", []):
        if call.get("tool") == "create_ticket":
            ticket_id = call.get("output", {}).get("ticket_id")
            break

    if not ticket_id:
        print_error("Failed to create ticket")
        return [False]

    print_success(f"Ticket created: ID={ticket_id}")
    time.sleep(1)

    # Step 2: Get ticket
    print(f"\n{Colors.YELLOW}→ Step 2: Retrieving ticket details...{Colors.RESET}")
    get_msg = f"Get ticket {ticket_id}"
    get_response = make_request(get_msg)

    ticket_found = False
    for call in get_response.get("tool_calls", []):
        if call.get("tool") == "get_ticket":
            ticket_found = call.get("output", {}).get("found", False)
            break

    if not ticket_found:
        print_error("Failed to retrieve ticket")
        return [False]

    print_success(f"Ticket retrieved successfully")
    time.sleep(1)

    # Step 3: Append note
    print(f"\n{Colors.YELLOW}→ Step 3: Adding resolution note...{Colors.RESET}")
    note_msg = f"Append note to ticket-{ticket_id}: Issue resolved by restarting application server"
    note_response = make_request(note_msg)

    note_added = False
    for call in note_response.get("tool_calls", []):
        if call.get("tool") == "append_note":
            note_added = call.get("output", {}).get("ok", False)
            break

    if not note_added:
        print_error("Failed to append note")
        return [False]

    print_success(f"Resolution note added")

    print()
    print_success("Complete workflow PASSED")

    return [True]


def main():
    """
    Main test runner
    """
    print(f"\n{Colors.BOLD}{Colors.CYAN}")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║        MCP TOOLS TEST SUITE - DevOps Agent                        ║")
    print("║        Testing 3 tools: create_ticket, get_ticket, append_note    ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print(f"{Colors.RESET}\n")

    # Check API is running
    print_info(f"Testing connection to {BASE_URL}...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print_success("API is reachable")
            health = response.json()
            if health.get("mcp_server_ready"):
                print_success("MCP server is ready")
            else:
                print_error("MCP server is not ready!")
                return
        else:
            print_error(f"API returned status {response.status_code}")
            return
    except Exception as e:
        print_error(f"Cannot connect to API: {str(e)}")
        print_info("Make sure the API is running: python agent_api.py")
        return

    print()

    # Run all tests
    all_results = []

    # Tool 1: create_ticket
    results_1 = test_tool_1_create_ticket()
    all_results.extend(results_1)

    time.sleep(2)

    # Tool 2: get_ticket
    results_2 = test_tool_2_get_ticket()
    all_results.extend(results_2)

    time.sleep(2)

    # Tool 3: append_note
    results_3 = test_tool_3_append_note()
    all_results.extend(results_3)

    time.sleep(2)

    # Combined workflow
    results_combined = test_combined_workflow()
    all_results.extend(results_combined)

    # Final summary
    print_header("FINAL TEST SUMMARY")

    total_tests = len(all_results)
    passed_tests = sum(all_results)
    failed_tests = total_tests - passed_tests
    success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

    print(f"{Colors.BOLD}Total Tests: {total_tests}{Colors.RESET}")
    print(f"{Colors.GREEN}{Colors.BOLD}Passed: {passed_tests}{Colors.RESET}")
    print(f"{Colors.RED}{Colors.BOLD}Failed: {failed_tests}{Colors.RESET}")
    print(f"{Colors.CYAN}{Colors.BOLD}Success Rate: {success_rate:.1f}%{Colors.RESET}")
    print()

    # Tool breakdown
    print(f"{Colors.BOLD}Tool Breakdown:{Colors.RESET}")
    print(f"  Tool 1 (create_ticket): {sum(results_1)}/{len(results_1)} passed")
    print(f"  Tool 2 (get_ticket):    {sum(results_2)}/{len(results_2)} passed")
    print(f"  Tool 3 (append_note):   {sum(results_3)}/{len(results_3)} passed")
    print(f"  Combined workflow:      {sum(results_combined)}/{len(results_combined)} passed")
    print()

    if failed_tests == 0:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ ALL TESTS PASSED!{Colors.RESET}")
    else:
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠ Some tests failed. Review output above.{Colors.RESET}")

    print()


if __name__ == "__main__":
    main()