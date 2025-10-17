# ACES - Ace Combat Expansion System
----------------------------------------------------------------
A GUI tool to simplify the process of adding a new entry to AC7's aircraft datatables or editing existing ones in the process of creating aircraft addons.

The Data folder is the folder where the input datatables (PlayerPlaneDataTable, SkinDataTable, AircraftViewerDataTable) are located - those which the manipulations will be performed on. The default one is the folder with vanilla datatables, packaged inside the executable. You can also select the locations of individual datatables separately. The program accepts datatables in both .uasset and .json format.

You can either add a new entry, or edit/delete an existing one. You can manipulate both PPDT and SDT at once, AVDT is managed automatically.
To use an existing aircraft as a template for a new one, switch to edit mode, select the desired aircraft, and switch back to add mode.
Adding PlaneStringID and special weapon IDs is required. PlaneID, if left empty, will automatically be set to the first unused PlaneID. Plane stats, if left empty, will default to F/A-18F stats.
Every entry is required to have at least one skin. You can change the skins' order number in the plane's skin list, in case you want to skip the Osea/Erusea/Special/Campaign skins, and enable/disable the emblems.
To delete an existing plane entry, simply press the Delete button next to the plane entry selector. The datatables will be automatically saved.

The program saves its output as .uasset + .uexp in a folder named Output in the same location as the executable. If the folder does not exist, it will be created automatically.

After the program completes the task, it will set the output directory as the working directory, so that you can continue working on the same datatables if need be.

UAssetAPI is used to ensure this program's proper functionality.
https://github.com/atenfyr/UAssetAPI