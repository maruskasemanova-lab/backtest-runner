import databento as db
import argparse
import os
from datetime import date

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download L2 data from Databento")
    parser.add_argument("--api_key", required=True, help="Databento API Key")
    parser.add_argument("--ticker", default="NVDA", help="Ticker symbol")
    parser.add_argument(
        "--start_date", default="2026-02-03", help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end_date",
        default="2026-02-06",
        help="Exclusive end date (YYYY-MM-DD). Example: 2026-02-06 includes 2026-02-05 session.",
    )
    parser.add_argument("--output_dir", default="data/l2", help="Output directory")

    args = parser.parse_args()

    print(
        f"Downloading L2 data for {args.ticker} from {args.start_date} to {args.end_date}..."
    )

    try:
        client = db.Historical(args.api_key)

        # Ensure output directory exists
        os.makedirs(args.output_dir, exist_ok=True)

        output_file = os.path.join(
            args.output_dir, f"{args.ticker}_{args.start_date}_{args.end_date}.mbn"
        )

        data = client.timeseries.get_range(
            dataset="XNAS.ITCH",  # Nasdaq TotalView-ITCH
            symbols=args.ticker,
            start=args.start_date,
            end=args.end_date,
            schema="mbp-10",  # Market by Price, 10 levels
            stype_in="raw_symbol",
            limit=None,  # Download all
        )

        # Save to file
        # We can either save as DBN (Databento Binary) or convert to other formats.
        # Keeping as DBN is efficient for storage, but we might want to convert to DataFrame for easier immediate usage if it fits in memory.
        # For now, let's keep it efficiently on disk as a file that we can replay/load.

        # Actually proper way with client is to stream to file usually, but get_range returns a DBNStore object which is in-memory or can be saved.
        data.to_file(output_file)

        print(f"Successfully downloaded to {output_file}")

        # Inspect first few rows to verify
        df = data.to_df()
        print("Data Preview:")
        print(df.head())
        print(df.columns)

    except Exception as e:
        print(f"Error downloading data: {e}")
