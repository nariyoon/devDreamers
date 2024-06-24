
# Define for updating image to UI
uimsg_update_callback = None

# Callback function for sending image to UI
def set_uimsg_update_callback(callback):
    # print("Callback function parameter sent.")
    global uimsg_update_callback
    uimsg_update_callback = callback



def sendMsgToUI(msg):
    print("send command to UI(len: ", len(msg), ")")
    # send callback to UI
    
    # recv_callback(msg)
    if uimsg_update_callback:
        print("Callback function is called.")
        uimsg_update_callback(msg)
    else:
        print("No callback function set for image update.")
