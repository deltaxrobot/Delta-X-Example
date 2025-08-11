#ifndef _DELTAXROBOT_

#define _DELTAXROBOT_

#if defined(ARDUINO) && ARDUINO >= 100
  #include "arduino.h"
#else
  #include "WProgram.h"
#endif

#define DEBUG_SERIAL  Serial

struct GcodeProgram
{
  String Name;
  String Value;
  uint16_t NewLinePostion = 0;
  bool isStop = true;
};

class DeltaXRobot
{
  public:  
    DeltaXRobot();
//    ~DeltaXrobot();

    HardwareSerial* GcodeSerial;
    bool IsCreatingProgram = false;
    bool IsProgramRunning = false;
	bool IsOk = true;
    String ReceiveString = "";
    GcodeProgram* ProgramList;
    int ProgrameCount = 0;
    
    void SetSerial(HardwareSerial* gcodeSerial);
    void Home();
    void MoveZ(float z);
    void MoveXY(float x, float y);
    void Gcode(String gcode);
    void Execute();
    void Run(String programName);
    void BeginGcode(String programName);
    void EndGcode();
    void WaitOk();
	bool SerialEvent();
	bool IsAllStop();
	bool IsProgramStop(String programName);
	bool IsSelectingProgram(String programName);

	private:
	bool isStop = true;
	GcodeProgram* selectingProgram = NULL;

    void sendGcode(String gcode);

};

#endif
