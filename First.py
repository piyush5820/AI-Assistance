import speech_recognition as sr

print("Listing microphones...\n")

for index, name in enumerate(sr.Microphone.list_microphone_names()):
    print(f"{index}: {name}")
