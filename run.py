#!/usr/bin/env python3
"""
Launcher script for Video Transcription Tool
Choose between the original monolithic version or the new modular version
"""

import sys
import os

def main():
    print("Video Transcription Tool Launcher")
    print("=" * 40)
    print("1. Run Modular Version (Recommended)")
    print("2. Run Original Version")
    print("3. Exit")
    print()
    
    while True:
        try:
            choice = input("Enter your choice (1-3): ").strip()
            
            if choice == "1":
                print("\nStarting Modular Version...")
                try:
                    from main_app import main
                    main()
                except ImportError as e:
                    print(f"Error: Could not import modular version: {e}")
                    print("Make sure all module files are present:")
                    print("- gui.py")
                    print("- audio_processor.py")
                    print("- transcription_engine.py")
                    print("- file_operations.py")
                    print("- main_app.py")
                break
                
            elif choice == "2":
                print("\nStarting Original Version...")
                try:
                    # Import the original monolithic code
                    exec(open('main_original.py').read())
                except FileNotFoundError:
                    print("Error: Original version file not found.")
                    print("The original code has been replaced with the modular version.")
                break
                
            elif choice == "3":
                print("Exiting...")
                sys.exit(0)
                
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")
                
        except KeyboardInterrupt:
            print("\nExiting...")
            sys.exit(0)
        except Exception as e:
            print(f"Error: {e}")
            print("Please try again.")

if __name__ == "__main__":
    main()
