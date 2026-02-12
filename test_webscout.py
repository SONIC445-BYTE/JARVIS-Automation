try:
    from webscout import PhindSearch
    
    def test_search():
        print("Testing WebScout...")
        phind = PhindSearch()
        results = phind.ask("Who is the president of the USA in 2025?")
        print("Results:")
        print(results)
        # Webscout usually returns a generator or string
        if hasattr(results, '__iter__') and not isinstance(results, str):
             for chunk in results:
                 print(chunk, end="", flush=True)
        else:
             print(results)

except ImportError:
    print("WebScout not installed or PhindSearch missing")

if __name__ == "__main__":
    test_search()
