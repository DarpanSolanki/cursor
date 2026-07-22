# JIRA AITDP Effectiveness — write 0–1 fraction

`customfield_11676` (AITDP Effectiveness as %) is a float whose **UI multiplies by 100**. Write `0.75` for 75% — never `75` (shows 7500%). Peer: SDCP-11013=`0.78`. After write: if raw `> 1`, wrong scale.
