#include "DeltaXRobot.h"

DeltaXRobot DeltaX;

void setup() 
{
	Serial.begin(115200);
  DeltaX.SetSerial(&Serial1);

  DeltaX.Gcode("G28");
  DeltaX.Gcode("G01 Z-350");
  DeltaX.Gcode("G01 X-100");
  DeltaX.Gcode("G02 I100 J0 X-100 Y0");
  DeltaX.Gcode("G03 I100 J0 X-100 Y0");
  
  DeltaX.BeginGcode("subprogram1");

  DeltaX.Home();
  DeltaX.MoveZ(-300);
  DeltaX.MoveZ(-270);
  DeltaX.MoveZ(-300);
  DeltaX.MoveZ(-270);
  DeltaX.MoveZ(-300);
  DeltaX.MoveZ(-270);

  DeltaX.EndGcode();
  
  DeltaX.BeginGcode("subprogram2");
  
  DeltaX.Home();
  DeltaX.MoveZ(-300);
  DeltaX.MoveXY(100,100);
  DeltaX.MoveXY(-100, 100);
  DeltaX.MoveXY(-100, -100);
  DeltaX.MoveXY(100, -100);
  DeltaX.Gcode("G01 X0 Y0");
  DeltaX.Gcode("G01 Z-330");
  
  DeltaX.EndGcode();

  DeltaX.Run("subprogram1");
}

void loop() 
{
  DeltaX.Execute();
  
  if (DeltaX.IsAllStop() == true && DeltaX.IsSelectingProgram("subprogram1") == true)
  {
    DeltaX.Run("subprogram2");
  }
}
