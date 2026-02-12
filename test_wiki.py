import wikipedia

def test_wiki():
    print("Testing Wikipedia...")
    try:
        # Set user agent to avoid blocking if required
        wikipedia.set_lang("en")
        
        query = "President of the United States"
        print(f"Querying: {query}")
        
        # Summary
        summary = wikipedia.summary(query, sentences=3)
        print(f"\nSummary:\n{summary}")
        
        if "Trump" in summary:
            print("\n[SUCCESS] Wikipedia returned Trump!")
        elif "Biden" in summary:
            print("\n[WARNING] Wikipedia returned Biden (Old?)")
        else:
            print("\n[INFO] returned neither explicitly in first 3 sentences.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_wiki()
