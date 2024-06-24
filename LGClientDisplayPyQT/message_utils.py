
# Define for updating image to UI
image_update_callback = None

# Callback function for sending image to UI
def set_image_update_callback(callback):
    # print("Callback function parameter sent.")
    global image_update_callback
    image_update_callback = callback



def sendMsgToUI(msg):
    print("send command to UI(len: ", len(msg), ")")
    # send callback to UI
    
    # recv_callback(msg)
    if image_update_callback:
        print("Callback function is called.")
        image_update_callback(msg)
    else:
        print("No callback function set for image update.")
