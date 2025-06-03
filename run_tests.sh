#!/bin/bash
# Thoth Test Runner Script

set -e  # Exit on error

echo "🦉 Thoth Test Runner"
echo "===================="

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse command line arguments
TEST_TYPE=${1:-"all"}
COVERAGE=${2:-"yes"}

# Function to run tests
run_tests() {
    local test_type=$1
    local test_args=""

    case $test_type in
        "smoke")
            echo -e "${YELLOW}Running smoke tests...${NC}"
            test_args="-m smoke"
            ;;
        "unit")
            echo -e "${YELLOW}Running unit tests...${NC}"
            test_args="-m unit"
            ;;
        "integration")
            echo -e "${YELLOW}Running integration tests...${NC}"
            test_args="-m integration"
            ;;
        "all")
            echo -e "${YELLOW}Running all tests...${NC}"
            test_args=""
            ;;
        *)
            echo -e "${RED}Unknown test type: $test_type${NC}"
            echo "Usage: $0 [smoke|unit|integration|all] [yes|no]"
            exit 1
            ;;
    esac

    # Add coverage if requested
    if [ "$COVERAGE" = "yes" ]; then
        test_args="$test_args --cov=src/thoth --cov-report=term-missing --cov-report=html:htmlcov"
    fi

    # Run tests
    pytest $test_args
}

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}pytest is not installed. Please install with: pip install -e .[test]${NC}"
    exit 1
fi

# Create test environment file if it doesn't exist
if [ ! -f .env.test ]; then
    echo -e "${YELLOW}Creating .env.test file...${NC}"
    cp .env.example .env.test
fi

# Run the tests
run_tests $TEST_TYPE

# Check the exit status
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"

    if [ "$COVERAGE" = "yes" ]; then
        echo -e "${YELLOW}Coverage report generated in htmlcov/index.html${NC}"
    fi
else
    echo -e "${RED}❌ Some tests failed!${NC}"
    exit 1
fi
