#include "DeltaXRobot.h"

DeltaXRobot::DeltaXRobot()
{
  DEBUG_SERIAL.begin(115200);

  
}

void DeltaXRobot::SetSerial(HardwareSerial* gcodeSerial)
{
  GcodeSerial = gcodeSerial;
  GcodeSerial->begin(115200);

  GcodeSerial->println("IsDelta");
  GcodeSerial->println("IsDelta");
}

void DeltaXRobot::Home()
{
  sendGcode("G28");
  WaitOk();
}

void DeltaXRobot::MoveZ(float z)
{
  String gc ="G01 Z";
  gc += z;
  sendGcode(gc);
  WaitOk();
}

void DeltaXRobot::MoveXY(float x, float y)
{
  String gc = "G01 X";
  gc += x;
  gc += " Y";
  gc += y;
  sendGcode(gc);
  WaitOk();
}

void DeltaXRobot::Gcode(String gcode)
{
    sendGcode(gcode);
    WaitOk();
}

void DeltaXRobot::Execute()
{
	SerialEvent();

	if (IsOk == true && selectingProgram->isStop == false)
	{
		if (selectingProgram->Value.length() < selectingProgram->NewLinePostion + 3)
		{
			selectingProgram->NewLinePostion = 0;
			selectingProgram->isStop = true;
			return;
		}
		int newLineCharPos = selectingProgram->Value.indexOf('\n', selectingProgram->NewLinePostion);
		String transportGcode = selectingProgram->Value.substring(selectingProgram->NewLinePostion, newLineCharPos);
		selectingProgram->NewLinePostion = newLineCharPos + 1;

		sendGcode(transportGcode);
		IsOk = false;
	}
}

void DeltaXRobot::Run(String programName)
{
  for(int i = 0; i < ProgrameCount; i++)
  {
    if (ProgramList[i].Name == programName)
    {
		selectingProgram = &ProgramList[i];
		selectingProgram->isStop = false;
		return;
    }
  }
}

void DeltaXRobot::BeginGcode(String programName)
{
  IsCreatingProgram = true;

  //Add new program
  
  ProgrameCount++;

  GcodeProgram *listTemp = new GcodeProgram[ProgrameCount];

  for (uint8_t index = 0; index < (ProgrameCount - 1); index++)
  {
    listTemp[index] = ProgramList[index];
  }

  if (ProgramList != NULL)
  {
    delete[] ProgramList;
  }

  ProgramList = listTemp;
  
  GcodeProgram program;
  program.Name = programName;
 
  ProgramList[ProgrameCount - 1] = program;
  selectingProgram = &ProgramList[ProgrameCount - 1];
}

void DeltaXRobot::EndGcode()
{
  IsCreatingProgram = false;
  selectingProgram = NULL;
}

void DeltaXRobot::WaitOk()
{  
  if (IsCreatingProgram == true)
  {
    return;
  }
  
  while (1)
  {
	  if (SerialEvent() == true)
		  return;
  }
}

bool DeltaXRobot::SerialEvent()
{
	if (GcodeSerial->available())
	{
		char c = GcodeSerial->read();
		if (c == '\n' || c == '\r')
		{
			if (ReceiveString == "Ok" || ReceiveString == "ok")
			{			
        ReceiveString = "";	
				IsOk = true;
				return true;
			}
     
      ReceiveString = "";
			return false;
		}
		else
		{
			ReceiveString += (char)c;
     
		}
	}

	return false;
}

bool DeltaXRobot::IsAllStop()
{
	for (int i = 0; i < ProgrameCount; i++)
	{
		if (ProgramList[i].isStop == false)
			return false;
	}
	return true;
}

bool DeltaXRobot::IsProgramStop(String programName)
{
	for (int i = 0; i < ProgrameCount; i++)
	{
		if (ProgramList[i].Name == programName)
		{
			return selectingProgram->isStop;
		}
	}
}

bool DeltaXRobot::IsSelectingProgram(String programName)
{
	if (selectingProgram == NULL)
		return false;

	if (selectingProgram->Name == programName)
		return true;
	else
		return false;
}

void DeltaXRobot::sendGcode(String gcode)
{
  if (IsCreatingProgram == true)
  {
    selectingProgram->Value += gcode +"\n";

	return;
  }

  GcodeSerial->println(gcode);

  IsOk = false;
}
