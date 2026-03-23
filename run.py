import subprocess
import sys

def main():
    """Entry point for the Streamlit UI via Poetry script."""
    # We use python -m streamlit to ensure we use the environment's streamlit
    subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"] + sys.argv[1:])

if __name__ == "__main__":
    main()
