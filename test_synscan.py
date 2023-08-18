from motors import motors

'''Goto example'''
smc=motors()
#Synchronize mount actual position to (0,0)
smc.set_pos(0,0)
#Move forward and wait to finish
smc.goto(0,10,synchronous=True)

print("Done 1")

#smc.track(0.1,0.1)




#Return to original position and exit without wait
#smc.goto(0,0,synchronous=False)
