import csv
import sys
import os
import argparse


def get_rows(filepath, num_rows):
    """Read the first N rows from a CSV file."""
    rows = []
    with open(filepath, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for _ in range(num_rows):
            row = next(reader, None)
            if row is None:
                break
            rows.append(row)
    return rows


def detect_header_rows(filepath):
    """Show the first few rows so the user can decide how many are headers."""
    print(f"\nFirst 5 rows of '{os.path.basename(filepath)}':")
    with open(filepath, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i >= 5:
                break
            print(f"  Row {i + 1}: {row}")


def validate_headers(input_files, num_header_rows):
    """Check that all files share identical header rows (columns and order)."""
    if num_header_rows == 0:
        return True

    reference_headers = get_rows(input_files[0], num_header_rows)
    reference_columns = reference_headers[-1] if reference_headers else []

    all_match = True
    for filepath in input_files[1:]:
        file_headers = get_rows(filepath, num_header_rows)
        file_columns = file_headers[-1] if file_headers else []

        if file_headers != reference_headers:
            print(f"\nMismatch: '{os.path.basename(filepath)}' vs '{os.path.basename(input_files[0])}'")

            ref_set = set(reference_columns)
            file_set = set(file_columns)
            missing = ref_set - file_set
            extra = file_set - ref_set

            if missing:
                print(f"  Columns missing from this file : {sorted(missing)}")
            if extra:
                print(f"  Extra columns in this file    : {sorted(extra)}")
            if not missing and not extra and file_columns != reference_columns:
                print(f"  Same columns but different order:")
                print(f"    Expected : {reference_columns}")
                print(f"    Got      : {file_columns}")
            if num_header_rows > 1 and file_columns == reference_columns:
                print(f"  Column row matches but upper header rows differ.")

            all_match = False

    return all_match


def combine_csvs(input_files, output_file, num_header_rows):
    """Append CSVs vertically, writing headers only from the first file."""
    total_data_rows = 0

    with open(output_file, "w", newline="", encoding="utf-8") as outf:
        writer = csv.writer(outf)

        for i, filepath in enumerate(input_files):
            with open(filepath, "r", newline="", encoding="utf-8-sig") as inf:
                reader = csv.reader(inf)
                rows_written = 0

                for row_num, row in enumerate(reader):
                    is_header_row = row_num < num_header_rows
                    if is_header_row and i > 0:
                        continue  # Skip duplicate headers from subsequent files
                    writer.writerow(row)
                    if not is_header_row:
                        rows_written += 1

            total_data_rows += rows_written
            print(f"  Added {rows_written:,} data rows from: {os.path.basename(filepath)}")

    return total_data_rows


def main():
    parser = argparse.ArgumentParser(
        description="Combine multiple CSV files vertically into one output file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python combine_csvs.py file1.csv file2.csv file3.csv -o combined.csv
  python combine_csvs.py *.csv -o combined.csv --header-rows 2
  python combine_csvs.py file1.csv file2.csv -o combined.csv --no-header
        """,
    )
    parser.add_argument("input_files", nargs="+", help="CSV files to combine (in order)")
    parser.add_argument("-o", "--output", required=True, help="Output CSV file path")
    parser.add_argument(
        "--header-rows",
        type=int,
        default=None,
        help="Number of header rows (default: auto-detect by prompting)",
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="Files have no header rows (equivalent to --header-rows 0)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output file if it already exists",
    )

    args = parser.parse_args()

    # Validate input files exist
    missing = [f for f in args.input_files if not os.path.isfile(f)]
    if missing:
        for f in missing:
            print(f"Error: File not found: {f}")
        sys.exit(1)

    if len(args.input_files) < 2:
        print("Error: At least two input files are required.")
        sys.exit(1)

    # Check output file
    if os.path.exists(args.output) and not args.force:
        answer = input(f"Output file '{args.output}' already exists. Overwrite? [y/N]: ").strip().lower()
        if answer != "y":
            print("Aborted.")
            sys.exit(0)

    # Determine number of header rows
    if args.no_header:
        num_header_rows = 0
    elif args.header_rows is not None:
        num_header_rows = args.header_rows
    else:
        detect_header_rows(args.input_files[0])
        while True:
            try:
                val = input("\nHow many header rows do these files have? [default: 1]: ").strip()
                num_header_rows = int(val) if val else 1
                if num_header_rows < 0:
                    raise ValueError
                break
            except ValueError:
                print("Please enter a non-negative integer.")

    print(f"\nUsing {num_header_rows} header row(s).")
    print(f"Validating column layout across {len(args.input_files)} files...")

    if not validate_headers(args.input_files, num_header_rows):
        print("\nColumn mismatch detected. Fix the files above or use --no-header to skip validation.")
        sys.exit(1)

    if num_header_rows > 0:
        print("All files have matching columns and layout.")

    print(f"\nCombining files into: {args.output}")
    total = combine_csvs(args.input_files, args.output, num_header_rows)

    print(f"\nDone. {total:,} total data rows written to '{args.output}'.")


if __name__ == "__main__":
    main()
