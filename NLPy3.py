from word2number import w2n
from wit import Wit
import json
import os
import sounddevice as sd
from scipy.io.wavfile import write
import tkinter as tk

# Initialize NLPy client
client = Wit("JVFT24TSKYIBPDR5I4PIASTD7Y6JIDA3")

# Dictionaries for ease of use
type_to_operator = {
    'assign': " = ",
    'plus': " += ",
    'sub': " -= ",
    'mult': " *= ",
    'div': " /= ",
}

comp_dict = {
    'eq': " == ",
    'gt': " > ",
    'lt': " < ",
}

# Track required tabbing
tabbing = 0

# Record audio setup
fs = 44100
seconds = 5


# Record audio to output.wav
def record():
    myrecording = sd.rec(int(seconds * fs), samplerate=fs, channels=2)
    sd.wait()
    write('output.wav', fs, myrecording)


# Print code with proper indenting
def output(text):
    output_str = ""
    for i in range(tabbing):
        output_str = output_str + "\t"
    output_str += text
    return output_str


# Send and parse message based on text
def message_text(text):
    resp = client.message(text)
    return parse_response(resp)


# Send and parse message based on audio
def message_voice(audio_clip):
    resp = None
    with open(audio_clip, 'rb') as f:
        resp = client.speech(f, {'Content-Type': 'audio/wav'})

    return parse_response(resp)


# Parse a string of raw text into usable IDs
def parse_id(value):
    if " dot " in value:
        return parse_id(value[:value.index(" dot ")]) + "." + parse_id(value[value.index(" dot ") + 5:])

    output_val = None
    try:
        output_val = w2n.word_to_num(value)
        if "negative" in value:
            output_val *= -1
    except:
        output_val = value

    return str(output_val)


# Parse the response returned by wit.ai
def parse_response(resp):
    """
    #Debugging print
    print('Full response: \n' + json.dumps(resp, indent=2))
    """
    global tabbing

    intent = resp['intents'][0]
    if intent['name'] in ['assign', 'sub', 'plus', 'mult', 'div']:
        valueJSON = None
        value = None

        if "id:rval" in resp["entities"] and "id:lval" in resp["entities"]:
            valueJSON = resp["entities"]["id:rval"][0]
            value = valueJSON["body"]
        elif "integer:integer" in resp["entities"] and "id:lval" in resp["entities"]:
            value = parse_id(resp["entities"]["integer:integer"][0]["body"])
        elif "fn_rval:fn_rval" in resp["entities"] and "id:lval" in resp["entities"]:
            function_call = resp["entities"]["fn_rval:fn_rval"][0]["body"]
            value = message_text(function_call)
        elif intent['name'] == 'assign' and 'empty_list:empty_list' in resp["entities"]:
            value = "[]"
        else:
            print(resp)
            raise Exception("Unrecognized input tokens for arithmetic")

        value = value.strip("\t")
        return output(resp["entities"]["id:lval"][0]["body"] + type_to_operator[intent['name']] + str(value))
    elif intent['name'] == 'for':
        if "id:iterator" in resp["entities"] and "id:iterable" in resp["entities"]:
            value = "\n" + output("for " + resp["entities"]["id:iterator"][0]["body"] + " in ")
            value += "range(" if ("range:range" in resp["entities"]) else ""
            value += parse_id(resp["entities"]["id:iterable"][0]["body"])
            value += ")" if ("range:range" in resp["entities"]) else ""
            value += ":"
            tabbing += 1
            return value
        else:
            print(resp)
            raise Exception("Unrecognized tokens for for loop")
    elif intent['name'] == 'fn_call':
        if "id:function" in resp["entities"]:
            fn_call = parse_id(resp["entities"]["id:function"][0]["body"]) + "("

            if "id:param" in resp["entities"]:
                fn_call = fn_call + parse_id(resp["entities"]["id:param"][0]["body"])

                for param in resp["entities"]["id:param"][1:]:
                    value = parse_id(param["body"])
                    fn_call = fn_call + ", " + value

            fn_call = fn_call + ")"
            return output(fn_call)
    elif intent['name'] == 'if':
        if "if_content:if_content" in resp["entities"]:
            value = "if " + message_text(resp["entities"]["if_content:if_content"][0]["body"]).strip("\t") + ":"
            value = "\n" + output(value)
            tabbing += 1
            return value
    elif intent['name'] in ['eq', 'gt', 'lt']:
        if "id:lcomp" in resp["entities"] and "id:rcomp" in resp["entities"]:
            return output(
                ("not " if "id:not" in resp["entities"] else "") +
                parse_id(resp["entities"]["id:lcomp"][0]["body"]) +
                comp_dict[intent['name']] +
                parse_id(resp["entities"]["id:rcomp"][0]["body"])
            )
    elif intent['name'] == 'elif':
        tabbing -= 1
        if "if_content:if_content" in resp["entities"]:
            value = "elif " + message_text(resp["entities"]["if_content:if_content"][0]["body"]).strip("\t") + ":"
            value = output(value)
            tabbing += 1
            return value
    elif intent['name'] == 'else':
        tabbing -= 1
        value = output("else:")
        tabbing += 1
        return value
    elif intent['name'] in ['end_if', 'end_loop']:
        tabbing -= 1
        return ""
    elif intent['name'] == 'print':
        if "id:rval" in resp["entities"]:
            value = output("print(" + parse_id(resp["entities"]["id:rval"][0]["body"]) + ")")
            return value
    elif intent['name'] == 'mod':
        if len(resp["entities"]["id:param"]) == 2:
            value = output(parse_id(resp["entities"]["id:param"][0]["body"]) + " % "
                           + parse_id(resp["entities"]["id:param"][1]["body"]))
            return value


if __name__ == "__main__":
    script = open("NLPy_output.py", "w+")

    # GUI setup
    window = tk.Tk()
    window.title("NLPy Transpiler")
    window.configure(background='black')
    window.minsize(1000, 500)

    output_text = tk.Label(window, background='black', fg='green', height=5, width=100, justify=tk.LEFT, font=("fixedsys", 15))
    output_text.pack(pady=40)

    instr = tk.Text(window, height=2, width=100, background='black', fg='green', font=("fixedsys", 13))
    instr.insert(tk.END, "Enter queries here")
    instr.pack(pady=20)

    label = tk.Label(fg='red', background='black', width=100, height=2)

    def submit():
        try:
            str_value = message_text(instr.get("1.0", tk.END))
            instr.delete('1.0', tk.END)
            script.write(str_value + "\n")
            label['text'] = str_value
            output_text['text'] += str_value + "\n"
            print(str_value)
        except:
            label['text'] = "Error reading input"

    def clicked_record():
        record()
        try:
            str_value = message_voice("output.wav")
            script.write(str_value + "\n")
            label['text'] = str_value
            output_text['text'] += str_value + "\n"
            print(str_value)
        except:
            label['text'] = "Error reading input"

    def stop_nlpy():
        script.close()
        exit()

    button_layout = tk.Frame(window, bg='black')
    button_layout.pack(side=tk.TOP)

    instrButton = tk.Button(text="Submit Command", command=submit, bg='black', borderwidth=5, fg='green')
    instrButton.pack(in_=button_layout, side=tk.LEFT, padx=15)

    record_button = tk.Button(text="Record", command=clicked_record, bg='black', borderwidth=5, fg='green')
    record_button.pack(in_=button_layout, side=tk.LEFT, padx=15)

    quit_button = tk.Button(text="Save + Quit", command=stop_nlpy, bg='black', borderwidth=5, fg='green')
    quit_button.pack(in_=button_layout, side=tk.LEFT, padx=15)

    label.pack(pady=20)

    def submit_enter(event):
        submit()

    window.bind('<Return>', submit_enter)
    window.mainloop()


"""
print(message_text("Assign x to y"))
print(message_text("Set var to equal"))
print(message_text("add five to a"))
print(message_text("decrease var by seventeen"))
print(message_text("multiply y by three thousand eight hundred seventeen"))
print(message_text("divide x by eight"))

print(message_text("loop through array using x"))
print(message_text("add one to a"))
print(message_text("end the loop"))

print(message_text("Call function on params and x and y"))
print(message_text("Call method"))

print(message_text("partition of ten"))
print(message_text("Let x equal pair of six"))
"""

"""
print(message_text("let x equal toast mod avocado"))
print(message_text("if toast isn't less than avocado"))
print(message_text("increase x by one"))
print(message_text("else if avocado isn't equal to toast"))
print(message_text("add one to y"))
print(message_text("else"))
print(message_text("call method"))

print(message_text("Let x equal a dot append x"))
"""

"""
print(message_text("let x equal the empty list"))
print(message_text("assign ten to y"))
print(message_text("loop through the range y using z"))
print(message_text("Call x dot append on z"))
print(message_text("end the for loop"))
print(message_text("output x"))
"""

"""
print(message_text("let counter equal one hundred"))
print(message_text("loop through the range counter using i"))
print(message_text("Let n equal i"))
print(message_text("Let prime equal one"))
print(message_text("add two to n"))
print(message_text("assign n to k"))
print(message_text("subtract two from k"))
print(message_text("loop through the range k using factor"))
print(message_text("let x equal factor"))
print(message_text("increment x by two"))
print(message_text("Assign n mod x to result"))
print(message_text("if result equals zero"))
print(message_text("set prime to zero"))
print(message_text("end if"))
print(message_text("end the for loop"))
print(message_text("if prime equals one"))
print(message_text("output n"))
"""