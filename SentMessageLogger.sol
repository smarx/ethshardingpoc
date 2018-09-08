pragma solidity ^0.4.20;

contract SentMessageLogger {

  event SentMessage(
    uint indexed shard_ID,
    uint sendGas,
    address sendFromAddress,
    address sendToAddress,
    uint value,
    bytes data,
    uint indexed base,
    uint TTL
  );

  uint TTL = 30; // some number of blocks

  // public instead of external due to https://github.com/ethereum/solidity/issues/3493
  function send(uint _shard_ID, uint _sendGas, address _sendToAddress, bytes _data)
    public
    payable
  {
    uint base = block.number;
    uint value = msg.value;
    address sender = msg.sender;

    emit SentMessage(
      _shard_ID,
      _sendGas,
      msg.sender,
      _sendToAddress,
      msg.value,
      _data,
      block.number,
      TTL
    );
  }

}