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

  function send(uint _shard_ID, uint _sendGas, address _sendToAddress, bytes _data)
    external
    payable
  {
    uint base = block.number;
    uint value = msg.value;
    address sender = msg.sender;

    address(0x0123456789012345678901234567890123456789).transfer(msg.value);

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